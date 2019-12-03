$(document).ready(function(){

    document.getElementById("dismissTestingResults").onclick = function(){
        document.getElementById("testingResultsHolder").style.display = "none";
    }

    var speedtest_socket = io.connect('http://' + document.domain + '/speedtest');
    document.getElementById("speedtestButton").onclick = function(){
        speedtest_socket.emit('start_test', {data: 'start_test'});
        document.getElementById("testingSpinner").style.display = "inline-block";
        document.getElementById("testingResultsHolder").style.display = "none";
    };
    speedtest_socket.on('testing', function(msg) {
        document.getElementById("testingResults").textContent = msg.data
        document.getElementById("testingSpinner").style.display = "none";
        document.getElementById("testingResultsHolder").style.display = "inline-block";
    });

    var traffic_socket = io.connect('http://' + document.domain + '/traffic');
    traffic_socket.on('traffic', function(msg) {
        message = msg.data.trim().split(" ") || []
        timestamp = message[0]
        download = message[1]
        upload = message[2]
        document.getElementById("timestamp").textContent = timestamp
        document.getElementById("download").textContent = download
        document.getElementById("upload").textContent = upload
    });

    const config = {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: "Ping",
                backgroundColor: 'rgb(255, 99, 132)',
                borderColor: 'rgb(255, 99, 132)',
                data: [],
                fill: false,
            },
            {
                label: "Download",
                backgroundColor: 'rgb(65, 138, 84)',
                borderColor: 'rgb(65, 138, 84)',
                data: [],
                fill: false,
            },
            {
                label: "Upload",
                backgroundColor: 'rgb(73, 85, 166)',
                borderColor: 'rgb(73, 85, 166)',
                data: [],
                fill: false,
            }],
        },
        options: {
            responsive: true,
            title: {
                display: true,
                text: 'Real-Time Status'
            },
            tooltips: {
                mode: 'index',
                intersect: false,
            },
            hover: {
                mode: 'nearest',
                intersect: true
            },
            scales: {
                xAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: 'Time'
                    }
                }],
                yAxes: [{
                    display: true,
                    scaleLabel: {
                        display: true,
                        labelString: 'Value'
                    }
                }]
            }
        }
    };

    const context = document.getElementById('canvas').getContext('2d');

    const lineChart = new Chart(context, config);

    const source = new EventSource("/chart-data");

    source.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (config.data.labels.length === 30) {
            config.data.labels.shift();
            config.data.datasets[0].data.shift();
            config.data.datasets[1].data.shift();
            config.data.datasets[2].data.shift();
        }
        config.data.labels.push(data.time);
        config.data.datasets[0].data.push(data.ping);
        config.data.datasets[1].data.push(data.download);
        config.data.datasets[2].data.push(data.upload);
        lineChart.update();
    }

    console.log('Started!')
});