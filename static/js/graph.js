function loadPlayerGraph(elem) {
    var offset = new Date().getTimezoneOffset() * 1000 * 60;
    var url = "player_graph";
    if (elem.attr("weeksAgo")) {
        url += "?weeks_ago=" + elem.attr("weeksAgo");
    }
    
    $.ajax({
        url: url,
        success: function(data) {
            elem.removeClass('progress');
            
            count_graph = new Array();
            new_graph = new Array();
            for (key in data) {
                var time = data[key].time - offset;
                var playerCount = data[key].player_count;
                var newPlayers = data[key].new_players;
                
                count_graph.push([time, playerCount]);
                if (newPlayers >= 0) {
                    new_graph.push([time, newPlayers]);
                }
            }
            
            if (new_graph.length) {
                data = [{data: count_graph}, {data: new_graph, yaxis: 2}];
            } else {
                data = [count_graph];
            }
            
            $.plot(elem, data, {
                grid: {hoverable: true, backgroundColor: "#ffffff"},
                colors: ["#7E9BFF", "#F00"],
                series: {lines: { fill: true }},
                xaxes: [{mode: "time", minTickSize: [1, "day"], timeformat: "%b %d"}],
                yaxes: [{min: 0, max: 48, tickSize: 6, position: "right"}, {min: 0, max: 20}] });
        },
        error: function(data) {
        }
    });
}

function showGraphTooltip(x, y, contents) {
    $('<div id="graph-tooltip">' + contents + '</div>').css( {
        position: 'absolute',
        display: 'none',
        top: y - 12,
        left: x + 14,
        border: '1px solid #666',
        padding: '2px',
        'background-color': '#111',
        'color': '#fff'
    }).appendTo("body").show();
}

$(document).ready(function() {
    var previousPoint = null;
    $(".graph").bind("plothover", function (event, pos, item) {
        if (item) {
            if (previousPoint != item.dataIndex) {
                previousPoint = item.dataIndex;
                
                $("#graph-tooltip").remove();
                var time = item.datapoint[0];
                var count = item.datapoint[1];
                
                showGraphTooltip(item.pageX, item.pageY, count + (count == 1 ? ' player' : ' players'));
            }
        } else {
            $("#graph-tooltip").remove();
            previousPoint = null;
        }
    });
});