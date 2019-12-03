CREATE TABLE traffic
(
	recorded_at TIMESTAMP without TIME ZONE DEFAULT now(),
	upload numeric,
	download numeric
);

CREATE index traffic_recorded_at ON traffic(recorded_at);