CREATE TABLE pings
(
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
	destination text,
	ttl integer,
	bytes_received integer,
	pingtime numeric
);

CREATE index pings_recorded_at ON pings(recorded_at);