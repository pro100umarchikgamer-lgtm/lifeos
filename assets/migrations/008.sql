CREATE TABLE local_profiles (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 name TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('adult','child')), guardian_id TEXT REFERENCES local_profiles(id),
 archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)), revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
 CHECK((kind='adult' AND guardian_id IS NULL) OR (kind='child' AND guardian_id IS NOT NULL AND guardian_id<>id))
);
CREATE TABLE local_memberships (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES local_identity(id), workspace_id TEXT NOT NULL REFERENCES workspaces(id),
 profile_id TEXT NOT NULL REFERENCES local_profiles(id), role TEXT NOT NULL CHECK(role IN ('owner','viewer','contributor','manager')),
 permissions INTEGER NOT NULL CHECK(typeof(permissions)='integer' AND permissions BETWEEN 0 AND 7),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT,
 UNIQUE(workspace_id,profile_id)
);
INSERT INTO local_profiles(id,owner_id,workspace_id,name,kind,created_at,updated_at)
 SELECT id,id,workspace_id,'LifeOS','adult',created_at,created_at FROM local_identity;
INSERT INTO local_memberships(id,owner_id,workspace_id,profile_id,role,permissions,created_at,updated_at)
 SELECT id,id,workspace_id,id,'owner',7,created_at,created_at FROM local_identity;
