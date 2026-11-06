-- Move spent voice and image allowances onto the neutral bucket names.
-- anthropic -> voice, fal_ai -> image, including the :u:<hash> per-user
-- keys. A day that already has both keys is summed, then the legacy row
-- is deleted, so the allowance is neither doubled nor replenished.
-- Other buckets (moderation, model actions, voice outcomes) are left
-- as they are. schema_version 30 is not a same-schema match for a
-- binary that still reads only anthropic and fal_ai.

UPDATE cost_budget
SET calls = calls + (
    SELECT legacy.calls
    FROM cost_budget AS legacy
    WHERE legacy.day = cost_budget.day
      AND legacy.bucket = CASE
            WHEN cost_budget.bucket = 'voice' THEN 'anthropic'
            WHEN cost_budget.bucket = 'image' THEN 'fal_ai'
            WHEN cost_budget.bucket LIKE 'voice:u:%'
                THEN 'anthropic' || substr(cost_budget.bucket, 6)
            WHEN cost_budget.bucket LIKE 'image:u:%'
                THEN 'fal_ai' || substr(cost_budget.bucket, 6)
          END
)
WHERE (
    cost_budget.bucket IN ('voice', 'image')
    OR cost_budget.bucket LIKE 'voice:u:%'
    OR cost_budget.bucket LIKE 'image:u:%'
)
AND EXISTS (
    SELECT 1
    FROM cost_budget AS legacy
    WHERE legacy.day = cost_budget.day
      AND legacy.bucket = CASE
            WHEN cost_budget.bucket = 'voice' THEN 'anthropic'
            WHEN cost_budget.bucket = 'image' THEN 'fal_ai'
            WHEN cost_budget.bucket LIKE 'voice:u:%'
                THEN 'anthropic' || substr(cost_budget.bucket, 6)
            WHEN cost_budget.bucket LIKE 'image:u:%'
                THEN 'fal_ai' || substr(cost_budget.bucket, 6)
          END
);

INSERT INTO cost_budget (bucket, day, calls, created_at)
SELECT
    CASE
        WHEN bucket = 'anthropic' THEN 'voice'
        WHEN bucket = 'fal_ai' THEN 'image'
        WHEN bucket LIKE 'anthropic:u:%' THEN 'voice' || substr(bucket, 10)
        WHEN bucket LIKE 'fal_ai:u:%' THEN 'image' || substr(bucket, 7)
    END,
    day,
    calls,
    created_at
FROM cost_budget AS legacy
WHERE (
    bucket = 'anthropic'
    OR bucket = 'fal_ai'
    OR bucket LIKE 'anthropic:u:%'
    OR bucket LIKE 'fal_ai:u:%'
)
AND NOT EXISTS (
    SELECT 1
    FROM cost_budget AS target
    WHERE target.day = legacy.day
      AND target.bucket = CASE
            WHEN legacy.bucket = 'anthropic' THEN 'voice'
            WHEN legacy.bucket = 'fal_ai' THEN 'image'
            WHEN legacy.bucket LIKE 'anthropic:u:%'
                THEN 'voice' || substr(legacy.bucket, 10)
            WHEN legacy.bucket LIKE 'fal_ai:u:%'
                THEN 'image' || substr(legacy.bucket, 7)
          END
);

DELETE FROM cost_budget
WHERE bucket IN ('anthropic', 'fal_ai')
   OR bucket LIKE 'anthropic:u:%'
   OR bucket LIKE 'fal_ai:u:%';
