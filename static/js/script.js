$(document).ready(function() {
    $('#load-spinning2').click(function(event) {
        event.preventDefault();  // Prevent the default behavior

        // Make an AJAX GET request to fetch spinning2 content
        $.ajax({
            url: '/show_spinning2',
            type: 'GET',
            success: function(response) {
                // Inject the returned content into the content-area div
                $('#content-area').html(response);
            },
            error: function() {
                alert('Error loading the spinning2 content');
            }
        });
    });
});
