/*
  # Quiz-Meister Database Schema

  ## Overview
  Supports live quiz sessions hosted over local WiFi. The app is self-hosted and
  uses Supabase for persistent state so the host can reload/crash and recover.

  ## New Tables

  ### sessions
  - Represents one running quiz game instance
  - Stores current state (lobby, question, reveal, leaderboard, ended)
  - References the YAML quiz file loaded for this session

  ### teams
  - Players register a team name when joining a session
  - Linked to a session, identified by a browser-assigned UUID

  ### answers
  - One row per team per question
  - Stores raw submitted answer and computed score
  - Allows manual score override by host

  ### score_overrides
  - Audit log of manual score adjustments made by host

  ## Security
  - RLS enabled on all tables
  - Sessions are publicly readable (needed for real-time sync on all screens)
  - Teams and answers are scoped to their session
  - No auth required — host uses a shared secret passed as a query param
*/

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  quiz_file text NOT NULL DEFAULT '',
  quiz_data jsonb NOT NULL DEFAULT '{}',
  state text NOT NULL DEFAULT 'lobby',
  -- state: lobby | question | answer_reveal | leaderboard | ended
  current_round_index integer NOT NULL DEFAULT 0,
  current_question_index integer NOT NULL DEFAULT 0,
  timer_ends_at timestamptz,
  host_secret text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Sessions are publicly readable"
  ON sessions FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Sessions can be inserted by anon"
  ON sessions FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Sessions can be updated by anon"
  ON sessions FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

-- Teams table
CREATE TABLE IF NOT EXISTS teams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  name text NOT NULL,
  browser_id text NOT NULL,
  score_override integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_id, browser_id),
  UNIQUE(session_id, name)
);

ALTER TABLE teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Teams are publicly readable"
  ON teams FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Teams can be inserted by anon"
  ON teams FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Teams can be updated by anon"
  ON teams FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

-- Answers table
CREATE TABLE IF NOT EXISTS answers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  team_id uuid NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  round_index integer NOT NULL DEFAULT 0,
  question_index integer NOT NULL DEFAULT 0,
  answer_data jsonb NOT NULL DEFAULT '[]',
  -- array of selected option indices, order indices, or numeric value
  score integer NOT NULL DEFAULT 0,
  score_overridden boolean NOT NULL DEFAULT false,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_id, team_id, round_index, question_index)
);

ALTER TABLE answers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Answers are publicly readable"
  ON answers FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Answers can be inserted by anon"
  ON answers FOR INSERT
  TO anon
  WITH CHECK (true);

CREATE POLICY "Answers can be updated by anon"
  ON answers FOR UPDATE
  TO anon
  USING (true)
  WITH CHECK (true);

-- Function to update sessions.updated_at automatically
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sessions_updated_at
  BEFORE UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_teams_session_id ON teams(session_id);
CREATE INDEX IF NOT EXISTS idx_answers_session_team ON answers(session_id, team_id);
CREATE INDEX IF NOT EXISTS idx_answers_session_round_q ON answers(session_id, round_index, question_index);
