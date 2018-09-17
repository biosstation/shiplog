$(document).ready(function() {
    $('#eventLog').dataTable( {
        "searching": false,
        "order": [[ 0, "desc" ]],
	"pageLength": 100
    } );
    $('#wireLog').dataTable( {
        "searching": false,
        "order": [[ 1, "desc" ]],
	"pageLength": 100
    } );
} );
