"""Notes: the application's own data. Each user sees and changes only their own."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ...models import Note
from ..deps import DbDep, UserDep
from ..schemas import NoteIn, NoteOut

router = APIRouter(prefix="/notes", tags=["notes"])


async def _own(db: DbDep, user: UserDep, note_id: int) -> Note:
    note = await db.get(Note, note_id)
    if note is None or note.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return note


@router.get("")
async def list_notes(user: UserDep, db: DbDep) -> list[NoteOut]:
    """This user's notes, the most recently changed first."""
    rows = await db.execute(
        select(Note).where(Note.user_id == user.id).order_by(Note.updated_at.desc(), Note.id.desc())
    )
    return [NoteOut.model_validate(row) for row in rows.scalars()]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_note(body: NoteIn, user: UserDep, db: DbDep) -> NoteOut:
    """Keep a new note."""
    note = Note(user_id=user.id, title=body.title.strip(), body=body.body)
    db.add(note)
    await db.flush()
    await db.refresh(note)
    return NoteOut.model_validate(note)


@router.put("/{note_id}")
async def update_note(note_id: int, body: NoteIn, user: UserDep, db: DbDep) -> NoteOut:
    """Change a note."""
    note = await _own(db, user, note_id)
    note.title = body.title.strip()
    note.body = body.body
    await db.flush()
    await db.refresh(note)
    return NoteOut.model_validate(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, user: UserDep, db: DbDep) -> None:
    """Delete a note."""
    await db.delete(await _own(db, user, note_id))
