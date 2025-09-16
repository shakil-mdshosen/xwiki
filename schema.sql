-- Create your tool database first, then run this schema.

CREATE TABLE IF NOT EXISTS events (
  id BIGINT PRIMARY KEY,
  wiki VARCHAR(64) NOT NULL,
  namespace INT,
  title VARCHAR(512),
  user VARCHAR(255),
  normalized_user VARCHAR(255), -- lowercased for matching
  type VARCHAR(32),             -- edit/new/log
  minor TINYINT(1),
  patrolled TINYINT(1),
  bot TINYINT(1),
  comment TEXT,
  timestamp DATETIME,
  rev_id BIGINT NULL,
  page_id BIGINT NULL,
  log_type VARCHAR(64) NULL,
  log_action VARCHAR(64) NULL,
  server_url VARCHAR(255) NULL,
  raw JSON
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS state (
  name VARCHAR(64) PRIMARY KEY,
  val VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS allowed_users (
  username VARCHAR(255) PRIMARY KEY,
  role ENUM('viewer','admin') NOT NULL DEFAULT 'viewer'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS tracked_users (
  username VARCHAR(255) NOT NULL,
  normalized_username VARCHAR(255) NOT NULL,
  PRIMARY KEY (normalized_username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Helpful indexes
CREATE INDEX idx_events_ts ON events (timestamp);
CREATE INDEX idx_events_user ON events (normalized_user);
CREATE INDEX idx_events_wiki ON events (wiki);
CREATE INDEX idx_events_type ON events (type);