 $(document).ready(function () {

    var content = $('.content');
    var message_container = $('#jsonmessages');
    var messages_url = message_container.data('messages');
    var last = '';
    NProgress.configure({ showSpinner: false });

    $.add_message = function(text, css) {
        if (last !== text) {
            var css_class = 'alert-';
            if (css != undefined) {
                css_class += css;
            } else {
                css_class += 'warning';
            }
            var message_div = message_container.find('.message-template').clone();
            message_div.removeClass('message-template');
            message_div.find('span').text(text);
            message_div.addClass(css_class);
            message_container.append(message_div);
            message_container.show();
            last = text;
        }
    }

	$(document).ajaxError(function(event, request, settings) {
        // in case of ajax Error
        if (request.status === 500) {
	 	     $.add_message('An error occured with your request');
        }
	});

    $(document).ajaxComplete(function(event, xhr, settings) {
        // in case an ajax request is completed
        if (xhr.readyState < 4) {
            xhr.abort();
        } else {
            NProgress.done();
        }
    });

    $(document).ajaxSend(function() {
        // in case an ajax request is sent
        // This does NOT work with jquery datatables.
        NProgress.start();
    });

    $( document ).ajaxSuccess(function(event, xhr, settings) {
        if (settings.url != messages_url) {
            $.get( messages_url, function(data) {
                if (data.logout === false) {
                    for (var i=0; i < data.messages.length; i++) {
                        $.add_message(data.messages[i].message, data.messages[i].css);
                    }
                } else {
                    $.add_message('Logging out...', 'info');
                    setTimeout(
                        function(){
                            location.reload();
                        },
                        3000
                    );
                }
            });
        }
    });
});
