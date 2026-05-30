-- Camera capture taken at the moment a defect is detected.
--
-- DEFINITION ONLY. The dashboard reads from this table; it never writes.
-- Populating it (capturing the frame from the camera stream and inserting the
-- row) is the vision backend's job and is being done on a separate branch.
--
-- Apply with:  psql "$DB_URL" -f schema.sql   (idempotent)

CREATE TABLE IF NOT EXISTS defect_images (
    id           BIGSERIAL PRIMARY KEY,
    product_id   INTEGER     REFERENCES products(id),
    detection_id BIGINT      REFERENCES detections(id),
    station_id   INTEGER     REFERENCES stations(id),
    captured_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    content_type TEXT        NOT NULL DEFAULT 'image/jpeg',
    image        BYTEA       NOT NULL,
    metadata     JSONB       NOT NULL DEFAULT '{}'
);

-- Fast "latest image for this product" lookup, which is all the dashboard does.
CREATE INDEX IF NOT EXISTS defect_images_product_idx
    ON defect_images (product_id, captured_at DESC);
