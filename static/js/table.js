$(document).ready(function() {
    $('#eventLog').dataTable( {
        "searching": false,
        "order": [[ 0, "desc" ]]
    } );
    $('#wireLog').dataTable( {
        "searching": false,
        "order": [[ 1, "desc" ]]
    } );
} );
