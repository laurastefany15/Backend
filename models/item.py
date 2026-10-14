from dataclasses import asdict, dataclass

from database import get_db


@dataclass
class Item:
    id: int
    name: str
    description: str
    created_at: str

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
        )

    def to_dict(self):
        return asdict(self)

    @classmethod
    def list_all(cls):
        rows = get_db().execute(
            "SELECT id, name, description, created_at FROM items ORDER BY id"
        ).fetchall()
        return [cls.from_row(row) for row in rows]

    @classmethod
    def get_by_id(cls, item_id):
        row = get_db().execute(
            "SELECT id, name, description, created_at FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
        return cls.from_row(row) if row is not None else None

    @classmethod
    def create(cls, name, description):
        db = get_db()
        cursor = db.execute(
            "INSERT INTO items (name, description) VALUES (?, ?)",
            (name, description),
        )
        db.commit()
        return cls.get_by_id(cursor.lastrowid)

    @classmethod
    def update(cls, item_id, fields):
        if cls.get_by_id(item_id) is None:
            return None

        assignments = ", ".join(f"{field} = ?" for field in fields)
        db = get_db()
        db.execute(
            f"UPDATE items SET {assignments} WHERE id = ?",
            (*fields.values(), item_id),
        )
        db.commit()
        return cls.get_by_id(item_id)

    @staticmethod
    def delete(item_id):
        db = get_db()
        cursor = db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        db.commit()
        return cursor.rowcount > 0