"""Shared transaction helpers for a bounded post-training chain."""
def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS studio_chains (
        id TEXT PRIMARY KEY,training_id TEXT NOT NULL,version TEXT NOT NULL,
        checkpoint_id TEXT NOT NULL,spec TEXT NOT NULL,state TEXT NOT NULL,
        stage TEXT NOT NULL,evaluation_id TEXT,compression_id TEXT,export_id TEXT,
        error TEXT,created TEXT NOT NULL,updated TEXT NOT NULL)""")

def exists(db):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='studio_chains'").fetchone() is not None

def claim(db,chain_id,stage,child,source,stamp,mode=None):
    if chain_id is None:
        if exists(db) and db.execute("SELECT 1 FROM studio_chains WHERE state='running' LIMIT 1").fetchone():
            raise ValueError("post-training chain active or needs recovery")
        return
    row=db.execute("SELECT * FROM studio_chains WHERE id=? AND state='running'",(chain_id,)).fetchone()
    column={"evaluation":"evaluation_id","compression":"compression_id","export":"export_id"}[stage]
    expected=row["training_id"] if row and stage=="evaluation" else row["evaluation_id"] if row else None
    if not row or row["stage"]!=stage or row[column] is not None or expected!=source:
        raise ValueError("chain child ownership mismatch")
    if stage=="compression":
        import json
        if mode!=json.loads(row["spec"])["mode"]:
            raise ValueError("chain compression mode mismatch")
    db.execute("UPDATE studio_chains SET "+column+"=?,updated=? WHERE id=?",(child,stamp,chain_id))

def reject_child_recovery(db,id,columns):
    if exists(db) and any(db.execute("SELECT 1 FROM studio_chains WHERE "+c+"=? AND state='running'",(id,)).fetchone() for c in columns):
        raise ValueError("recover the parent chain instead")
