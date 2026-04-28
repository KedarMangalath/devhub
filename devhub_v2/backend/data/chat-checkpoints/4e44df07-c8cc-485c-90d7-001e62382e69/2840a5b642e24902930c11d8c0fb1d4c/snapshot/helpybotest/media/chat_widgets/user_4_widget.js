(function() {
    // Inject CSS
    const style = document.createElement('style');
    style.textContent = `
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: Arial, sans-serif;
        }

        #chat-widget {
            position: fixed;
            bottom:20px;
            right: 20px;
            width: 460px;
            height: 90%;
            border-radius: 15px;
            background: #fff;
            box-shadow: 0 5px 30px rgba(0, 0, 0, 0.2);
            display: none;
            flex-direction: column;
            z-index: 1001;
            overflow: hidden;
            transition: all 0.3s ease;
            font-family: 'Roboto', sans-serif;
        }

        #chat-header {
            background: #0b3d2c;
            color: #fff;
            padding: 15px 20px;
            font-size: 18px;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            height: 90px;
        }

        .header-text-container {
            display: flex;
            align-items: center;
            flex-grow: 1;
        }

        #chat-logo {
            width: 60px;
            height: 60px;
            border-radius: 8px;
            margin-right: 10px;
            object-fit: cover;
        }

        #carousel-container {
            background: #f8f9fa;
            padding: 5px;
            border-bottom: 1px solid #dee2e6;
        }

        #carousel {
            margin-bottom: 18px;
        }

        .card {
            border: 1px solid #ccc;
            padding: 0px;
            margin: 5px;
            border-radius: 15px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            width: calc(100% - 40px);
            box-sizing: border-box;
            height: 180px;
        }

        #chat-widget .button {
            padding: 8px 8px;
            margin: 5px;
            border: 1px solid #0b3d2c; 
            background-color: transparent;
            color: #0b3d2c; 
            border-radius: 20px;
            cursor: pointer;
            transition: background-color 0.3s, color 0.3s; 
        }
        
        #chat-widget .button:hover {
            background-color: #0b3d2c; 
            color: white; 
        }

        #chat-messages {
            flex: 1;
            padding: 10px;
            overflow-y: auto;
            background: #f8f9fa;
            scrollbar-width: thin;
            scrollbar-color: #0b3d2c #e0e0e0;
        }

        #chat-widget .message {
            margin-bottom: 14px;
            padding: 13px 13px;
            max-width: 70%;
            animation: fadeIn 0.3s ease;
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
            border-radius: 20px;
            position: relative;
        }

        #chat-widget .user-message {
            background-color: #0b3d2c;
            color: #fff;
            float: right;
            clear: both;
            font-size: 14px;
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
            border-bottom-right-radius: 0px;
            border-bottom-left-radius: 20px;
            padding-bottom: 25px;
        }

        #chat-widget .bot-message {
            font-family: Arial, sans-serif;
            background-color: #e9ecef;
            color: #343a40;
            float: left;
            clear: both;
            font-size: 14px;
            max-width: calc(100% - 65px);
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
            padding-bottom: 25px;
        }

        #chat-widget .timestamp {
            font-size: 10px;
            color: #6c757d;
            position: absolute;
            bottom: 5px;
            right: 10px;
        }

        #chat-widget .message-actions {
            position: absolute;
            bottom: 5px;
            left: 10px;
            display: flex;
            gap: 12px;
            align-items: center;
        }

        #chat-widget .share-button, #chat-widget .translate-button {
            background: none;
            border: none;
            color: #0b3d2c;
            font-size: 14px;
            cursor: pointer;
            padding: 5px;
            transition: all 0.3s ease;
            opacity: 0.7;
        }

        #chat-widget .share-button:hover, #chat-widget .translate-button:hover {
            opacity: 1;
            transform: scale(1.1);
        }
        

        #chat-widget .share-options {
            position: absolute;
            bottom: -40px;
            left: 0;
            display: flex;
            gap: 12px;
            background: white;
            padding: 8px;
            border-radius: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 10;
        }

        #chat-widget .share-options button {
            background: none;
            border: none;
            padding: 5px;
            cursor: pointer;
            transition: transform 0.2s ease;
        }

        #chat-widget .share-options button:hover {
            transform: scale(1.15);
        }


        #chat-input {
            display: flex;
            align-items: center;
            padding: 15px;
            background: #fff;
            border-top: 1px solid #dee2e6;
            height: 80px;
        }

        #chat-input input {
            flex: 1;
            padding: 10px 15px;
            border: 1px solid #ced4da;
            border-radius: 20px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.3s ease;
        }

        #chat-input input:focus {
            border-color: #0b3d2c;
        }

        #chat-input button {
            background-color: #0b3d2c;
            color: #fff;
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            margin-left: 10px;
            cursor: pointer;
            transition: background-color 0.3s ease;
            font-size: 17px;
            padding: 10px;
        }

        #chat-input button:hover {
            background-color: #0b3d2c;
        }

        #chat-button-container {
            position: fixed;
            bottom: 0px;
            right: 0px;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 1000;
            transition: all 0.3s ease;
        }

        #we-are-here-image {
            width:180px;
            height: auto;
            transition: all 0.3s ease;
            z-index: 999;
        }

        #chat-button {
            width: 65px;
            height: 65px;
            border-radius: 50%;
            background-color: #0b3d2c;
            color: #fff;
            font-size: 24px;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
            margin-top: 0px;
        }

        #chat-button-container:hover {
            transform: scale(1.1);
        }

        #chat-button-container:hover #we-are-here-image {
            transform: translateY(-5px);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @keyframes slideIn {
            from { transform: translateY(100%); }
            to { transform: translateY(0); }
        }

        @keyframes loadingDots {
            0% { content: '.'; }
            33% { content: '..'; }
            66% { content: '...'; }
            100% { content: ''; }
        }

        .loading-dots::after {
            content: '';
            animation: loadingDots 1.5s infinite;
        }

        #chat-messages::-webkit-scrollbar {
            width: 10px;
        }

        #chat-messages::-webkit-scrollbar-track {
            background: ##0b3d2c;
            border-radius: 10px;
        }

        #chat-messages::-webkit-scrollbar-thumb {
            background-color: #0b3d2c;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }

        #chat-messages::-webkit-scrollbar-thumb:hover {
            background-color: #0b3d2c;
        }

        #minimize-chat {
            background: none;
            border: none;
            color: #fff;
            font-size: 18px;
            cursor: pointer;
            padding: 5px;
            transition: all 0.3s ease;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        #minimize-chat:hover {
            background-color: rgba(255, 255, 255, 0.2);
        }

        #minimize-chat:focus {
            outline: none;
        }

        #minimize-chat i {
            transition: transform 0.3s ease;
        }

        #minimize-chat:hover i {
            transform: scale(1.2);
        }

        .card img, .card iframe {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 15px;
        }

        #chat-footer {
            padding: 5px 0;
            text-align: center;
            background-color: #f8f9fa;
            border-top: 1px solid #dee2e6;
        }

        #chat-footer small {
            font-size: 10px;
            color: #6c757d;
        }

        #chat-footer a {
            color: #0b3d2c;
            text-decoration: none;
            font-weight: bold;
        }

        #translation-disclaimer {
            font-size: 10px;
            color: #666;
            text-align: center;
            padding: 5px;
            background: #f8f9fa;
            border-top: 1px solid #dee2e6;
            display: none;
        }

        .message-image-container {
            margin: 10px 0;
            max-width: 100%;
        }
        
        .message-image-container img {
            max-width: 100%;
            border-radius: 8px;
            height: auto;
            display: block;
            margin: 0 auto;
        }
        
        .bot-message img {
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        
        .bot-message img:hover {
            transform: scale(1.05);
        }



        @media (max-width: 768px) {
            #chat-widget {
                width: 100%;
                height: 100%;
                bottom: 0;
                right: 0;
                border-radius: 0;
            }
            #chat-button-container {
                bottom: 20px;
                right: 20px;
            }
            #we-are-here-image {
                width: 180px;
            }
            #chat-widget .message {
                max-width: 80%;
            }
        }
    `;
    document.head.appendChild(style);

    // Load external scripts and styles
    const resources = [
        { type: 'link', href: "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css", rel: "stylesheet" },
        { type: 'script', src: "https://code.jquery.com/jquery-3.6.0.min.js" },
        { type: 'script', src: "https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" },
        { type: 'link', href: "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css", rel: "stylesheet" },
        { type: 'script', src: "https://cdn.jsdelivr.net/npm/slick-carousel@1.8.1/slick/slick.min.js" },
        { type: 'link', href: "https://cdn.jsdelivr.net/npm/slick-carousel@1.8.1/slick/slick.css", rel: "stylesheet" },
        { type: 'script', src: "https://cdn.jsdelivr.net/npm/marked/marked.min.js" },
    ];

    let translationEnabled = ;
    let currentLanguage = 'ml'; // Set to Malayalam by default
    let originalMessages = new Map();

    function loadResource(resource) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`[src="${resource.src}"], [href="${resource.href}"]`)) {
                resolve();
                return;
            }

            let element;
            if (resource.type === 'script') {
                element = document.createElement('script');
                element.src = resource.src;
            } else if (resource.type === 'link') {
                element = document.createElement('link');
                element.href = resource.href;
                element.rel = resource.rel;
            }
            element.onload = resolve;
            element.onerror = reject;
            document.head.appendChild(element);
        });
    }

    Promise.all(resources.map(loadResource))
        .then(() => {
            initChatWidget();
        })
        .catch(error => console.error('Error loading resources:', error));

    function initChatWidget() {
        if (document.getElementById('chat-widget')) {
            return;
        }

        const chatButtonContainer = document.createElement('div');
        chatButtonContainer.id = 'chat-button-container';

        const weAreHereImage = document.createElement('img');
        weAreHereImage.id = 'we-are-here-image';
        weAreHereImage.src = '' || '#';
        weAreHereImage.alt = "We are here";
        
        const chatButton = document.createElement('button');
        chatButton.id = 'chat-button';
        chatButton.innerHTML = '<i class="fas fa-comment"></i>';
        
        chatButtonContainer.appendChild(weAreHereImage);
        chatButtonContainer.appendChild(chatButton);
        
        const chatWidget = document.createElement('div');
        chatWidget.id = 'chat-widget';
        
        chatWidget.innerHTML = `
            <div id="chat-header">
                <div class="header-text-container">
                    <img id="chat-logo" src="${'' || '#'}" alt="Chatbot Logo">
                    <div data-original-text="Chat">Chat</div>
                </div>
                <button id="minimize-chat"><i class="fas fa-minus"></i></button>
            </div>

            <div id="chat-messages">
                <div id="carousel-container">
                    <div id="carousel">
                        <!-- Carousel items will be dynamically added here -->
                    </div>
                </div>

                <div id="buttons">
                    <!-- Buttons will be dynamically added here -->
                </div>

                <div class="message bot-message">
                    <p data-original-text="welcome to test">welcome to test</p>
                    <div class="timestamp">${getCurrentTime()}</div>
                </div>
            </div>
            <div id="chat-input">
                <input type="text" id="message" placeholder="Type a message..." data-original-placeholder="Type a message...">
                <button id="mic-button"><i class="fas fa-microphone"></i></button>
                <button id="send-button"><i class="fas fa-paper-plane"></i></button>
            </div>
            <div id="translation-disclaimer">
                Note: Automated translations may not be completely accurate. Please refer to English text for precise communication.
            </div>
            <div id="chat-footer">
                <small>Powered by <a href="https://helpybo.com" target="_blank">Helpybo AI Engine</a></small>
            </div>
        `;
        
        document.body.appendChild(chatButtonContainer);
        document.body.appendChild(chatWidget);
        
        chatButton.addEventListener('click', toggleChat);
        document.getElementById('minimize-chat').addEventListener('click', toggleChat);
        document.getElementById('send-button').addEventListener('click', sendMessage);
        document.getElementById('mic-button').addEventListener('click', startRecording);
        document.getElementById('message').addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                sendMessage();
            }
        });

        $('#carousel').slick({
            dots: true,
            infinite: true,
            speed: 300,
            slidesToShow: 1,
            slidesToScroll: 1,
            adaptiveHeight: true,
            arrows: false,
            autoplay: true,
            autoplaySpeed: 3000,
            centerMode: true,
            centerPadding: '0px'
        });

        adjustWidgetForMobile();
        window.addEventListener('resize', adjustWidgetForMobile);
    }

    async function translateAllMessages() {
        if (!translationEnabled) return; // Don't translate if disabled
        
        const messages = document.querySelectorAll('.message p');
        for (let message of messages) {
            const originalText = message.getAttribute('data-original-text') || message.textContent;
            if (!message.getAttribute('data-original-text')) {
                message.setAttribute('data-original-text', originalText);
            }
            
            if (currentLanguage !== 'en') {
                const translatedText = await translateText(originalText, currentLanguage);
                message.textContent = translatedText;
            } else {
                message.textContent = originalText;
            }
        }
    }

    async function translateStaticElements() {
        const messageInput = document.getElementById('message');
        const originalPlaceholder = messageInput.getAttribute('data-original-placeholder');
        if (currentLanguage !== 'en') {
            messageInput.placeholder = await translateText(originalPlaceholder, currentLanguage);
        } else {
            messageInput.placeholder = originalPlaceholder;
        }

        const headerText = document.querySelector('.header-text-container div');
        const originalHeader = headerText.getAttribute('data-original-text');
        if (currentLanguage !== 'en') {
            headerText.textContent = await translateText(originalHeader, currentLanguage);
        } else {
            headerText.textContent = originalHeader;
        }
    }

    async function translateText(text, targetLang) {
        if (targetLang === 'en') return text;
        
        try {
            const sentences = text.split(/(?<=[.!?])\s+/);
            const translatedSentences = await Promise.all(sentences.map(async (sentence) => {
                const response = await fetch('https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=' + targetLang + '&dt=t&q=' + encodeURIComponent(sentence));
                if (!response.ok) throw new Error('Translation failed');
                const data = await response.json();
                return data[0][0][0];
            }));
            return translatedSentences.join(' ');
        } catch (error) {
            console.error('Translation error:', error);
            return text;
        }
    }

    function toggleChat() {
        var chatWidget = document.getElementById('chat-widget');
        var chatButtonContainer = document.getElementById('chat-button-container');
        
        if (chatWidget.style.display === 'none' || chatWidget.style.display === '') {
            chatWidget.style.display = 'flex';
            chatButtonContainer.style.display = 'none';
            chatWidget.style.animation = 'slideIn 0.3s ease-out';
        } else {
            chatWidget.style.animation = 'slideIn 0.3s ease-out reverse';
            setTimeout(() => {
                chatWidget.style.display = 'none';
                chatButtonContainer.style.display = 'flex';
            }, 300);
        }

        if (chatWidget.style.display === 'flex') {
            document.getElementById('chat-messages').innerHTML = '';
            appendMessage("welcome to test", 'bot-message');
            sessionId = null;
        }

        adjustWidgetForMobile();
    }

    function adjustWidgetForMobile() {
        var chatWidget = document.getElementById('chat-widget');
        var chatButtonContainer = document.getElementById('chat-button-container');

        if (window.innerWidth <= 768) {
            chatWidget.style.width = '100%';
            chatWidget.style.height = '100%';
            chatWidget.style.bottom = '0';
            chatWidget.style.right = '0';
            chatWidget.style.borderRadius = '0';

            chatButtonContainer.style.bottom = '20px';
            chatButtonContainer.style.right = '20px';
        } else {
            chatWidget.style.width = '420px';
            chatWidget.style.height = '720px';
            chatWidget.style.bottom = '20px';
            chatWidget.style.right = '20px';
            chatWidget.style.borderRadius = '15px';

            chatButtonContainer.style.bottom = '40px';
            chatButtonContainer.style.right = '5px';
        }
    }

    async function appendMessage(content, className) {
        var chatMessages = document.getElementById('chat-messages');
        var messageContainer = document.createElement('div');
        messageContainer.classList.add('message-container');
        
        var messageDiv = document.createElement('div');
        messageDiv.classList.add('message', className);
        
        const paragraphs = content.split('\n');
        for (const paragraph of paragraphs) {
            const p = document.createElement('p');
            p.setAttribute('data-original-text', paragraph);
            p.innerHTML = formatMessage(paragraph, className === 'bot-message');
            messageDiv.appendChild(p);
        }
        
        var timestampDiv = document.createElement('div');
        timestampDiv.classList.add('timestamp');
        timestampDiv.textContent = getCurrentTime();
        
        messageDiv.appendChild(timestampDiv);
        
        messageContainer.appendChild(messageDiv);
        
        if (className === 'bot-message') {
            var actionContainer = document.createElement('div');
            actionContainer.classList.add('message-actions');
            
            var shareButton = document.createElement('button');
            shareButton.innerHTML = '<i class="fas fa-share-alt"></i>';
            shareButton.classList.add('share-button');
            shareButton.onclick = function(event) {
                event.stopPropagation();
                toggleShareOptions(event.target, content);
            };
            
            actionContainer.appendChild(shareButton);
        
            // Only add translation button if translation is enabled
            if (translationEnabled) {
                var translateButton = document.createElement('button');
                translateButton.innerHTML = '<i class="fas fa-language"></i>';
                translateButton.classList.add('translate-button');
                translateButton.onclick = function(event) {
                    event.stopPropagation();
                    translateMessage(messageDiv);
                };
                actionContainer.appendChild(translateButton);
            }
            
            messageDiv.appendChild(actionContainer);
        }
        
        chatMessages.appendChild(messageContainer);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function sendMessage() {
        var messageInput = document.getElementById('message');
        var message = messageInput.value.trim();
        if (message === '') return;

        appendMessage(message, 'user-message');
        messageInput.value = '';

        const waitingMessages = [
            "Your query is being processed",
            "Please wait patiently",
            "Fetching the best response for you"
        ];

        const randomMessage = waitingMessages[Math.floor(Math.random() * waitingMessages.length)];

        var loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'bot-message');
        loadingDiv.innerHTML = `${randomMessage}<span class="loading-dots"></span>`;
        document.getElementById('chat-messages').appendChild(loadingDiv);

        fetch('http://127.0.0.1:7000/chat/response/4/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                query: message,
                session_id: sessionId,
                is_new_session: sessionId === null,
                logo_url: ''
            })
        })
        .then(response => response.json())
        .then(data => {
            loadingDiv.remove();
            appendMessage(data.response, 'bot-message');
            sessionId = data.session_id;
        })
        .catch(error => console.error('Error:', error));
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    function getCurrentTime() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    function startRecording() {
        const micButton = document.getElementById('mic-button');
        const messageInput = document.getElementById('message');

        if (!('webkitSpeechRecognition' in window)) {
            alert('Speech recognition is not supported in your browser. Please use Chrome.');
            return;
        }

        if (!window.recognition) {
            window.recognition = new webkitSpeechRecognition();
            window.recognition.continuous = true;
            window.recognition.interimResults = true;
            window.recognition.maxAlternatives = 1;
            window.recognition.lang = 'en-US';

            window.recognition.onresult = function(event) {
                let current = event.resultIndex;
                let transcript = event.results[current][0].transcript;
                messageInput.value = transcript;
            };

            window.recognition.onstart = function() {
                micButton.innerHTML = '<i class="fas fa-microphone" style="color: red;"></i>';
                messageInput.placeholder = 'Listening...';
            };

            window.recognition.onend = function() {
                micButton.innerHTML = '<i class="fas fa-microphone"></i>';
                messageInput.placeholder = 'Type a message...';
            };

            window.recognition.onerror = function(event) {
                console.error('Recognition error:', event.error);
                micButton.innerHTML = '<i class="fas fa-microphone"></i>';
                messageInput.placeholder = 'Type a message...';
            };
        }

        if (micButton.querySelector('i').style.color !== 'red') {
            messageInput.value = '';
            window.recognition.start();
        } else {
            window.recognition.stop();
        }
    }

    function toggleShareOptions(button, message) {
        var messageContainer = button.closest('.message-container');
        var existingOptions = messageContainer.querySelector('.share-options');
        
        if (existingOptions) {
            existingOptions.remove();
            return;
        }
        
        var shareOptions = document.createElement('div');
        shareOptions.classList.add('share-options');
        
        var platforms = [
            { name: 'WhatsApp', icon: 'fab fa-whatsapp', color: '#25d366' },
            { name: 'Gmail', icon: 'fas fa-envelope', color: '#db4437' }
        ];
        
        platforms.forEach(platform => {
            var shareButton = document.createElement('button');
            shareButton.innerHTML = `<i class="${platform.icon}" style="color: ${platform.color};"></i>`;
            shareButton.title = platform.name;
            shareButton.onclick = function(e) {
                e.preventDefault();
                e.stopPropagation();
                shareToPlatform(platform.name, message);
            };
            shareOptions.appendChild(shareButton);
        });
        
        button.parentNode.insertBefore(shareOptions, button.nextSibling);
        
        document.addEventListener('click', function closeOptions(e) {
            if (!shareOptions.contains(e.target) && e.target !== button) {
                shareOptions.remove();
                document.removeEventListener('click', closeOptions);
            }
        });
    }

    function shareToPlatform(platform, message) {
        var encodedMessage = encodeURIComponent(message);
        var encodedUrl = encodeURIComponent(window.location.href);
        var url;

        switch(platform) {
            case 'WhatsApp':
                url = `https://wa.me/?text=${encodedMessage}%20${encodedUrl}`;
                break;
            case 'Gmail':
                url = `mailto:?subject=Chatbot%20Message&body=${encodedMessage}%0A%0A${encodedUrl}`;
                break;
        }

        window.open(url, '_blank', 'width=600,height=400');
    }

    function formatMessage(message, isBot) {
        if (isBot) {
            // First, identify and clean up the image section
            message = message.replace(/ Image:[\s\S]*?<img src="([^"]*)"[\s\S]*?>/g, function(match, src) {
                return `\n<div class="message-image-container"><img src="${src}" alt="Product Image" loading="lazy" onerror="this.style.display='none'"/></div>\n`;
            });
    
            // Remove any remaining image tag text artifacts
            message = message.replace(/<img src="/g, '');
            message = message.replace(/" alt="[^"]*" loading="lazy" onerror="[^"]*"\/>/g, '');
            message = message.replace(/ Image:.*$/gm, '');
            
            // Clean up any standalone code-like text
            message = message.replace(/<[^>]+>/g, '');
            
            // Clean up any remaining image-related artifacts
            message = message.replace(/\s*"?\s*alt=.*?>/g, '');
            message = message.replace(/\s*"?\s*loading=.*?>/g, '');
            message = message.replace(/\s*"?\s*onerror=.*?>/g, '');
            message = message.replace(/\s*"?\s*style\.display=.*?>/g, '');
            
            // Process URLs into proper image tags
            message = message.replace(/(https?:\/\/[^)\s]+\.(jpg|jpeg|png|gif|webp))/gi,
                '<div class="message-image-container"><img src="$1" alt="Product Image" loading="lazy" onerror="this.style.display=\'none\'"/></div>');
            
            // Remove any empty lines
            message = message.replace(/^\s*[\r\n]/gm, '');
            
            // Process remaining markdown
            return marked.parse(message);
        } else {
            return message
                .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
                .replace(/\n/g, '<br>');
        }
    }

    function sendButtonValue(value) {
        appendMessage(value, 'user-message');
        sendToServer(value);
    }

    function sendToServer(message) {
        const waitingMessages = [
            "Your query is being processed",
            "Please wait patiently",
            "Fetching the best response for you"
        ];

        const randomMessage = waitingMessages[Math.floor(Math.random() * waitingMessages.length)];

        var loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'bot-message');
        loadingDiv.innerHTML = `${randomMessage}<span class="loading-dots"></span>`;
        document.getElementById('chat-messages').appendChild(loadingDiv);

        fetch('http://127.0.0.1:7000/chat/response/4/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                query: message,
                session_id: sessionId,
                is_new_session: sessionId === null,
                logo_url: ''
            })
        })
        .then(response => response.json())
        .then(data => {
            loadingDiv.remove();
            appendMessage(data.response, 'bot-message');
            sessionId = data.session_id;
        })
        .catch(error => console.error('Error:', error));
    }

    async function translateMessage(messageDiv) {
        if (!translationEnabled) return; // Don't translate if disabled
        
        const paragraphs = messageDiv.querySelectorAll('p');
        for (const paragraph of paragraphs) {
            const originalText = paragraph.getAttribute('data-original-text') || paragraph.textContent;
            if (!paragraph.getAttribute('data-original-text')) {
                paragraph.setAttribute('data-original-text', originalText);
            }
    
            const translatedText = await translateText(originalText, currentLanguage);
            paragraph.textContent = translatedText;
        }
    
        const disclaimer = document.getElementById('translation-disclaimer');
        disclaimer.style.display = 'block';
    }
    
    function setInitialLanguage() {
        const browserLang = navigator.language.split('-')[0];
        const langSelector = document.getElementById('language-selector');
        const availableLangs = Array.from(langSelector.options).map(opt => opt.value);
        
        if (availableLangs.includes(browserLang)) {
            langSelector.value = browserLang;
            currentLanguage = browserLang;
            translateAllMessages().then(() => translateStaticElements());
        }
    }
    
    function toggleTranslationDisclaimer() {
        const disclaimer = document.getElementById('translation-disclaimer');
        if (currentLanguage !== 'en') {
            disclaimer.style.display = 'block';
        } else {
            disclaimer.style.display = 'none';
        }
    }
    
    // Initialize session variable
    let sessionId = null;
    
    // Initialize the chat widget when the page loads
    window.addEventListener('load', function() {
        // Load all required resources first
        Promise.all(resources.map(loadResource))
            .then(() => {
                initChatWidget();
                setInitialLanguage();
            })
            .catch(error => console.error('Error initializing chat widget:', error));
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        adjustWidgetForMobile();
    });
    
    // Handle click outside of share options
    document.addEventListener('click', function(e) {
        const shareOptions = document.querySelectorAll('.share-options');
        shareOptions.forEach(options => {
            if (!options.contains(e.target) && !e.target.classList.contains('share-button')) {
                options.remove();
            }
        });
    });


    document.addEventListener('click', function(e) {
        if (e.target.tagName === 'IMG' && e.target.closest('.message')) {
            const imgSrc = e.target.src;
            
            const modal = document.createElement('div');
            modal.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 1002;
                cursor: pointer;
            `;
            
            const modalImg = document.createElement('img');
            modalImg.src = imgSrc;
            modalImg.style.cssText = `
                max-width: 90%;
                max-height: 90%;
                object-fit: contain;
            `;
            
            modal.appendChild(modalImg);
            document.body.appendChild(modal);
            
            modal.onclick = function() {
                modal.remove();
            };
        }
    });


    // Handle visibility change
    document.addEventListener('visibilitychange', function() {
        if (document.hidden && window.recognition) {
            window.recognition.stop();
            const micButton = document.getElementById('mic-button');
            micButton.innerHTML = '<i class="fas fa-microphone"></i>';
            document.getElementById('message').placeholder = 'Type a message...';
        }
    });
    
    // Handle errors gracefully
    window.onerror = function(msg, url, lineNo, columnNo, error) {
        console.error('Error: ' + msg + '\nURL: ' + url + '\nLine: ' + lineNo + '\nColumn: ' + columnNo + '\nError object: ' + JSON.stringify(error));
        return false;
    };
    
    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
    });
    
    // Clean up resources when the window is closed
    window.addEventListener('beforeunload', function() {
        if (window.recognition) {
            window.recognition.stop();
        }
    });
    
})(); // End of IIFE