"""Tests for SQLite database layer."""

import threading

from src.utils.database import Database


class TestDatabase:
    def test_create_tables(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            # Tables should exist
            with db._lock:
                cur = db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                tables = {row["name"] for row in cur.fetchall()}
            assert "violations" in tables
            assert "evidence_files" in tables
            assert "cloud_queue" in tables
            assert "email_queue" in tables
        finally:
            db.close()

    def test_wal_mode(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            with db._lock:
                cur = db._conn.execute("PRAGMA journal_mode")
                mode = cur.fetchone()[0]
            assert mode == "wal"
        finally:
            db.close()

    def test_insert_and_get_violation(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            vid = db.insert_violation(
                violation_id="test-123",
                violation_type="no_helmet",
                confidence=0.92,
                plate_text="MH12AB1234",
                gps_lat=12.97,
                gps_lon=77.59,
            )
            assert vid == "test-123"

            v = db.get_violation("test-123")
            assert v is not None
            assert v["type"] == "no_helmet"
            assert v["confidence"] == 0.92
            assert v["plate_text"] == "MH12AB1234"
            assert v["status"] == "pending"
        finally:
            db.close()

    def test_update_violation_status(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            db.insert_violation("v1", "no_helmet", 0.9)
            db.update_violation_status("v1", "sent")
            v = db.get_violation("v1")
            assert v["status"] == "sent"
        finally:
            db.close()

    def test_get_violations_by_status(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            db.insert_violation("v1", "no_helmet", 0.9)
            db.insert_violation("v2", "red_light_jump", 0.8)
            db.update_violation_status("v1", "sent")

            pending = db.get_violations_by_status("pending")
            assert len(pending) == 1
            assert pending[0]["id"] == "v2"

            sent = db.get_violations_by_status("sent")
            assert len(sent) == 1
            assert sent[0]["id"] == "v1"
        finally:
            db.close()

    def test_evidence_files(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            db.insert_violation("v1", "no_helmet", 0.9)
            eid = db.insert_evidence_file("v1", "/path/frame.jpg", "frame", 1024, "abc123")
            assert eid > 0

            files = db.get_evidence_files("v1")
            assert len(files) == 1
            assert files[0]["file_path"] == "/path/frame.jpg"
            assert files[0]["file_hash"] == "abc123"
        finally:
            db.close()

    def test_cloud_queue(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            db.insert_violation("v1", "no_helmet", 0.9)
            qid = db.enqueue_cloud("v1")
            assert qid > 0

            pending = db.get_pending_cloud()
            assert len(pending) == 1
            assert pending[0]["violation_id"] == "v1"

            db.update_cloud_status(qid, "done", response_json='{"ok": true}')
            pending = db.get_pending_cloud()
            assert len(pending) == 0
        finally:
            db.close()

    def test_email_queue(self, tmp_db_path):
        db = Database(tmp_db_path)
        try:
            db.insert_violation("v1", "no_helmet", 0.9)
            qid = db.enqueue_email("v1")
            assert qid > 0

            pending = db.get_pending_emails()
            assert len(pending) == 1

            db.update_email_status(qid, "sent")
            pending = db.get_pending_emails()
            assert len(pending) == 0
        finally:
            db.close()

    def test_thread_safety(self, tmp_db_path):
        db = Database(tmp_db_path)
        errors = []

        def insert_violations(start, count):
            try:
                for i in range(count):
                    db.insert_violation(f"v-{start + i}", "no_helmet", 0.9)
            except Exception as e:
                errors.append(e)

        try:
            threads = [
                threading.Thread(target=insert_violations, args=(0, 20)),
                threading.Thread(target=insert_violations, args=(20, 20)),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not errors
            # All 40 should be present
            for i in range(40):
                assert db.get_violation(f"v-{i}") is not None
        finally:
            db.close()
