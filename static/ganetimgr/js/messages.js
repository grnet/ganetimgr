 $(document).ready(function () {

    $.add_message = function(text) {
    	var message_container = $('#jsonmessages');
    	var message_div = message_container.find('.message-template').clone();
    	message_div.removeClass('message-template');
    	message_div.find('span').text(text);
    	message_container.append(message_div);
	    $('.content').removeClass('loading');
	    message_container.show();
    }

	$(document).ajaxError(function() {
	 	$.add_message('An error occured with your request');
	});
});
