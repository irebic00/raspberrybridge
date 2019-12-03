#!/usr/bin/python

import io
import json
import re
import subprocess
import threading
import time

import psycopg2
import psycopg2.extras
from decorator import contextmanager
from flask import Flask, Response, render_template, make_response, copy_current_request_context
from flask_socketio import SocketIO, emit
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.dates import DateFormatter, SecondLocator
from matplotlib.figure import Figure
from psycopg2 import pool

from bin.params import ParameterHandler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
ph = ParameterHandler()


@contextmanager
def get_conn():
    db = pool.SimpleConnectionPool(1, 10, host='0.0.0.0',
                                   database=ph.db_name,
                                   user=ph.db_username,
                                   password=ph.db_password)
    con = db.getconn()
    try:
        yield con
    finally:
        db.putconn(con)


@app.route('/stats')
def index():
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        destination_overview_query = """
            SELECT
              destination,
              min(pingtime),
              round(avg(pingtime), 2) AS avg,
              max(pingtime)
            FROM
              pings
            WHERE
              recorded_at > now() - INTERVAL '1 hour'
            GROUP BY
              destination;
        """

        cur.execute(destination_overview_query)

        destinations = cur.fetchall()

    return render_template('index.html', destinations=destinations)


@socketio.on('start_test', namespace='/speedtest')
def speedtest(message):
    @copy_current_request_context
    def speedtest_handler():
        speedtest_cli = subprocess.Popen(['speedtest-cli --simple'],
                                         shell=True,
                                         stdout=subprocess.PIPE)
        while speedtest_cli.poll() is None:
            time.sleep(1)
        emit('testing', {'data': speedtest_cli.stdout.read().decode('utf-8')})
    t = threading.Thread(target=speedtest_handler)
    t.start()


@socketio.on('connect', namespace='/traffic')
def traffic():
    @copy_current_request_context
    def traffic_handler():
        traffic_cli = subprocess.Popen(['sudo ifstat -i ' + ph.outbound_interface + ' -t -b -w -n'],
                                       shell=True,
                                       stdout=subprocess.PIPE)

        while traffic_cli.poll() is None:
            output = traffic_cli.stdout.readline().decode('utf-8').strip()
            if output is not None:
                curr_time = download = upload = ''
                match_output = re.search(r'(\d\d:\d\d:\d\d)\s*(\d+\.\d+)\s*(\d+\.\d+)',
                                         ' '.join(output.split()))
                if match_output is not None:
                    curr_time = match_output.group(1)
                    upload = ('%2.2f' % (float(match_output.group(2))/1000)) + 'Mbps'
                    download = ('%2.2f' % (float(match_output.group(3))/1000)) + 'Mbps'

                parsed_output = curr_time + ' ' + download + ' ' + upload
                emit('traffic', {'data': parsed_output})
            time.sleep(1)
    t = threading.Thread(target=traffic_handler)
    t.start()


@app.route('/graphs/<destination>', methods=['POST', 'GET'])
def graph(destination):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        destination_history_query = """
            WITH intervals AS (
                SELECT
                  begin_time,
                  LEAD(begin_time)
                  OVER (
                    ORDER BY begin_time ) AS end_time
                FROM
                      generate_series(
                          now() - INTERVAL '1 hours',
                          now(),
                          INTERVAL '1 minutes'
                      ) begin_time
            )
            SELECT
              i.begin_time AT TIME ZONE 'Europe/Berlin' AS begin_time,
              i.end_time AT TIME ZONE 'Europe/Berlin' AS end_time,
              p.destination,
              count(p.pingtime),
              round(avg(p.pingtime),2) AS avg,
              max(p.pingtime),
              min(p.pingtime)
            FROM intervals i LEFT JOIN pings p
            ON p.recorded_at >= i.begin_time AND
              p.recorded_at < i.end_time
            WHERE 
              i.end_time IS NOT NULL
              AND destination = %s
            GROUP BY i.begin_time, i.end_time, p.destination
            ORDER BY i.begin_time ASC;
        """

        cur.execute(destination_history_query, (destination,))

        times = cur.fetchall()

    fig = Figure(figsize=(30, 8), dpi=80, facecolor='w', edgecolor='k', tight_layout=True)
    ax = fig.add_subplot(111)

    begin_times = [row['begin_time'] for row in times]

    maxs = [row['max'] for row in times]
    ax.plot_date(
        x=begin_times,
        y=maxs,
        label='max',
        linestyle='solid'
    )

    avgs = [row['avg'] for row in times]
    ax.plot_date(
        x=begin_times,
        y=avgs,
        label='avg',
        linestyle='solid'
    )

    mins = [row['min'] for row in times]
    ax.plot_date(
        x=begin_times,
        y=mins,
        label='min',
        linestyle='solid'
    )

    ax.set_xlabel('Time')
    ax.set_ylabel('Round Trip (ms)')
    ax.set_ylim(bottom=0)

    ax.xaxis_date()
    my_fmt = DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(my_fmt)
    ax.xaxis.set_major_locator(SecondLocator(interval=60))
    ax.legend()
    ax.grid()

    png_output = io.BytesIO()

    fig.set_canvas(FigureCanvasAgg(fig))
    fig.savefig(png_output, transparent=True, format='png')

    response = make_response(png_output.getvalue())
    response.headers['content-type'] = 'image/png'
    return response


@app.route('/graphs/traffic')
def live_traffic():
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        destination_history_query = """
            SELECT * FROM traffic WHERE recorded_at >= now() - INTERVAL '10 minutes';
        """

        cur.execute(destination_history_query)

        times = cur.fetchall()

    fig = Figure(figsize=(30, 8), dpi=80, facecolor='w', edgecolor='k', tight_layout=True)
    ax = fig.add_subplot(111)

    begin_times = [row['recorded_at'] for row in times]

    upload = [row['upload'] for row in times]
    ax.plot_date(
        x=begin_times,
        y=upload,
        label='upload',
        linestyle='solid'
    )

    download = [row['download'] for row in times]
    ax.plot_date(
        x=begin_times,
        y=download,
        label='download',
        linestyle='solid'
    )

    ax.set_xlabel('Time')
    ax.set_ylabel('Bandwidth')
    ax.set_ylim(bottom=0)

    ax.xaxis_date()
    my_fmt = DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(my_fmt)
    ax.xaxis.set_major_locator(SecondLocator(interval=60))
    ax.legend()
    ax.grid()

    png_output = io.BytesIO()

    fig.set_canvas(FigureCanvasAgg(fig))
    fig.savefig(png_output, transparent=True, format='png')

    response = make_response(png_output.getvalue())
    response.headers['content-type'] = 'image/png'
    return response


@app.route('/packetloss/<destination>')
def packetloss(destination):
    with get_conn() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        destination_history_query = """
        WITH intervals AS (
                SELECT
                  begin_time,
                  LEAD(begin_time)
                  OVER ( ORDER BY begin_time ) AS end_time
                  FROM generate_series(
                          now() - INTERVAL '1 hours',
                          now(),
                          INTERVAL '1 minutes'
                      ) begin_time
            )
            SELECT
              i.begin_time AT TIME ZONE 'Europe/Zagreb' AS begin_time,
              i.end_time AT TIME ZONE 'Europe/Zagreb' AS end_time,
              p.destination,
              count(*),
              round(avg(p.pingtime),2) AS avg,
              max(p.pingtime),
              min(p.pingtime)
            FROM intervals i LEFT JOIN pings p
            ON p.recorded_at >= i.begin_time AND
              p.recorded_at < i.end_time
            WHERE 
              i.end_time IS NOT NULL
              AND destination = 'www.amazon.de'
              AND p.pingtime IS NULL
            GROUP BY i.begin_time, i.end_time, p.destination
            ORDER BY i.begin_time ASC;
        """

        cur.execute(destination_history_query, (destination,))

        times = cur.fetchall()

    packets_lost = sum([row['count'] for row in times])
    if packets_lost is None:
        packets_lost = 0.0
    packets_lost_total = '%3.3f' % (packets_lost/(60.0 * 60.0)) + '% (' + str(packets_lost) + '/3600)'

    return packets_lost_total


@app.route('/chart-data')
def chart_data():
    def generate_random_data():
        get_last_traffic = """
        SELECT
            recorded_at,
            download,
            upload
        FROM traffic
        ORDER BY recorded_at DESC
        LIMIT 1
        """
        get_last_ping = """
        SELECT
            recorded_at::timestamp with time zone AT TIME ZONE 'Europe/Zagreb',
            pingtime
        FROM pings
        ORDER BY recorded_at DESC
        LIMIT 1
        """
        while True:
            with get_conn() as conn:
                cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cur.execute(get_last_traffic)
                traffics = cur.fetchall()
                cur.execute(get_last_ping)
                pings = cur.fetchall()
            timestamp = pings[0][0]
            ping = float(pings[0][1])
            download = float(traffics[0][1])
            upload = float(traffics[0][2])
            json_data = json.dumps(
                {'time': timestamp.strftime('%H:%M:%S'), 'ping': ping, 'download': download, 'upload': upload})
            yield f"data:{json_data}\n\n"
            time.sleep(1)

    return Response(generate_random_data(), mimetype='text/event-stream')


if __name__ == '__main__':
    app.run(port=80, host='0.0.0.0', debug=True, threaded=True)
