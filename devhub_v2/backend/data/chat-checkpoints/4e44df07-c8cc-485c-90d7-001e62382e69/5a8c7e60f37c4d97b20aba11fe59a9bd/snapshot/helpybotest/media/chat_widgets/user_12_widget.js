(function() {
    // Move variables to wider scope for debugging
    let activeFlow = null;
    let currentStep = 0;
    let sessionId = null;
    let userMessageCount = 0;
    let isProcessingClick = false;
    let leadState = {
        nameCollected: false,
        phoneCollected: false,
        name: '',
        phone: '',
        userId: null
    };
    let userSelections = {}; // Dynamic object to store all selections
    let translationEnabled = false;
    let leadsEnabled = false;
    let currentLanguage = 'ml'; // Set to Malayalam by default
    let originalMessages = new Map();
    let chatbotId = 9;
    let isFirstMessage = true;
    let widgetInitialized = false;

    // Debug logging function
    function debugLog(label, data) {
        console.log(`[ChatBot Debug] ${label}:`, data);
    }

    // Add centralized lead collection messages
    const LEAD_MESSAGES = {
        NAME_REQUEST: "Before we continue, could you please share your name?",
        PHONE_REQUEST: "Great! And your phone number please?",
        THANK_YOU: "Thank you for providing your information! Our team will contact you soon."
    };

    // Helper function to trigger lead collection
    function triggerLeadCollection() {
        console.log("Triggering lead collection");
        setTimeout(() => {
            appendMessage("Before we continue, could you please tell me your name?", 'bot-message');
            createLeadForm('name');
        }, 500);
    }

    // Helper function to check and trigger lead collection
    function checkAndTriggerLeadCollection() {
        console.log("Checking if lead collection should be triggered");
        if (!leadState.nameCollected) {
            setTimeout(() => {
                appendMessage("Before we continue, could you please tell me your name?", 'bot-message');
                createLeadForm('name');
            }, 800);
            return true;
        }
        return false;
    }

    // Single function to control lead collection flow
// Function to handle lead collection
function handleLeadCollection() {
    // First remove any existing lead forms to prevent duplicates
    document.querySelectorAll('.lead-form').forEach(form => form.remove());
    
    if (!leadState.nameCollected) {
        appendMessage(LEAD_MESSAGES.NAME_REQUEST, 'bot-message');
        createLeadForm('name');
        return true;
    } else if (!leadState.phoneCollected) {
        appendMessage(LEAD_MESSAGES.PHONE_REQUEST, 'bot-message');
        createLeadForm('phone');
        return true;
    }
    return false;
}
    // Inject CSS
    const style = document.createElement('style');
    style.textContent = `
        #chat-widget {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 460px;
    height: 80%;
    border-radius: 35px;
    background: #fff;
    box-shadow: 0 5px 30px rgba(0, 0, 0, 0.2);
    display: none;
    flex-direction: column;
    z-index: 9999;
    overflow: hidden;
    transition: all 0.3s ease;
    font-family: 'Roboto', sans-serif;
}

       #chat-header {
    background:#85c1ad;
    color: #fff;
    padding: 15px 20px;
    font-size: 18px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    height: 90px;
    position: relative;
    z-index: 1; /* Ensure the header is above the wave */
}

.wave {
    position: absolute;
    top: 10px; /* Adjust to align perfectly with the header */
    left: 0;
    width: 115%;
    height: 230px; /* Adjust the height of the wave */
    z-index: 0; /* Ensure the wave is below the header */
    overflow: hidden;
    transform: rotate(180deg);
}

.wave-path {
}

@keyframes waveAnimation {
    0% {
        d: path("M0,20 C150,50 350,0 500,20 L500,70 L0,50 Z");
        transform: translateX(0);
    }
    25% {
        d: path("M0,20 C150,70 350,10 500,20 L500,50 L0,50 Z");
    }
    50% {
        d: path("M0,20 C150,30 350,40 500,20 L500,50 L0,50 Z");
        transform: translateX(60px); 
    }
    75% {
        d: path("M0,20 C150,60 350,20 500,20 L500,50 L0,50 Z");
    }
    100% {
        d: path("M0,20 C150,50 350,0 500,20 L500,70 L0,50 Z");
        transform: translateX(0);
    }
}

        .header-text-container {
            display: flex;
            align-items: center;
            margin-top: 0px;
            margin-left: 5px;
        }

        #chat-logo {
            width: 70px;
            height: 70px;
            border-radius: 50%;
            margin-bottom: 0px;
            margin-right: 15px;
            object-fit: cover;
        }

        #chat-logo-button {
        position: relative;
            width: 50px;
            height: 50px;
            border-radius: 8px;
            margin-right: 0px;
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
            margin: 0px;
            border-radius: 15px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            width: calc(100% - 40px);
            box-sizing: border-box;
            height: 180px;
        }

        #chat-widget #chat-widget .button {
            padding: 8px 8px;
            margin: 5px;
            border: 1px solid #0b3d2c; 
            background-color: transparent;
            color: #0b3d2c; 
            border-radius: 20px;
            cursor: pointer;
            transition: background-color 0.3s, color 0.3s; 
        }
        
        #chat-widget #chat-widget .button:hover {
            background-color: #0b3d2c; 
            color: white; 
        }

       #chat-messages {
    flex: 1;
    padding: 10px;
    overflow-y: auto;
    scrollbar-color: #85c1ad;
    height: calc(100% - 80px);
    margin-top: 0px; /* Add margin to separate from the wave */
}

        #chat-widget #chat-widget .message {
            margin-bottom: 14px;
            padding: 13px 13px;
            max-width: 70%;
            animation: fadeIn 0.3s ease;
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
            border-radius: 23px;
            position: relative;
        }

        #chat-widget #chat-widget .user-message {
            background-color: #85c1ad;
            color: #fff;
            float: right;
            clear: both;
            font-size: 15px;
            border-top-left-radius: 20px;
            border-top-right-radius: 20px;
            border-bottom-right-radius: 0px;
            border-bottom-left-radius: 20px;
            padding-bottom: 17px;
            border-radius: 18px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
            .user-message p{
            margin-bottom:5px;
            }

        #chat-widget #chat-widget .bot-message {
            font-family: Arial, sans-serif;
            background-color:rgb(255, 255, 255);
            border: 2px solid #4f97de17;
            color: #343a40;
            float: left;
            clear: both;
            font-size: 14px;
            max-width: calc(100% - 65px);
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
            padding-bottom: 20px;
        }
            


        
#chat-widget #chat-widget .bot-message:before {
    content: "";
    z-index: -1;
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
        background: linear-gradient(-45deg, #85c1ad 0%, #85c1ad 100%);
    transform: translate3d(0px, 6px, 0) scale(0.95);
    filter: blur(7px);
    opacity: 0.4;
    transition: opacity 0.3s;
    border-radius: inherit;
}

/* 
* Prevents issues when the parent creates a 
* stacking context. (For example, using the transform
* property )
*/
#chat-widget #chat-widget .bot-message::after {
    content: "";
    z-index: -1;
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    background: inherit;
    border-radius: inherit;
}
        
                
        

        #chat-widget #chat-widget .timestamp {
            font-size: 10px;
            color:rgb(134, 142, 149);
            position: absolute;
            bottom: 5px;
            right: 7px;
        }

        #chat-widget #chat-widget .message-actions {
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
        
        #chat-widget #chat-widget .share-options {
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

        #chat-widget #chat-widget .share-options button {
            background: none;
            border: none;
            padding: 5px;
            cursor: pointer;
            transition: transform 0.2s ease;
        }

        #chat-widget #chat-widget .share-options button:hover {
            transform: scale(1.15);
        }

        #chat-input {
    display: flex;
    align-items: center;
    padding: 15px;
    background: #fff;
    height: 80px;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
    box-shadow: 0 -4px 15px rgba(0, 0, 0, 0.05);
    position: sticky;
    bottom: 0px; /* Adjust based on footer height */
    z-index: 10;
}

        

        #chat-input button {
            background-color:#85c1ad;
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
            background-color:#85c1ad;
        }

        #chat-button-container {
            position: fixed;
            bottom: 70px !important;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            justify-content: center; /* Center the button within the container */
            gap: 10px;
            z-index: 999;
            transition: all 0.3s ease;
        }

        

        #chat-button {
        position: relative;
            width: 70px;
            height: 70px;
            border-radius: 50%;
            color: #fff;
            font-size: 24px;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            margin-top: 0px;
            z-index: 1001;
        }
            

        #chat-button:before {
            content: "";
            z-index: -1;
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            background: linear-gradient(-45deg, #85c1ad 0%, #ffffff 100%);
            transform: translate3d(0px, 5px, 0) scale(0.95);
            filter: blur(10px);
            opacity: var(0.7);
            transition: opacity 0.3s;
            border-radius: inherit;
        }
        
        /* 
        * Prevents issues when the parent creates a 
        * stacking context. (For example, using the transform
        * property )
        */
        #chat-button::after {
            content: "";
            z-index: -1;
            position: absolute;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            background: inherit;
            border-radius: inherit;
        }
                
        

        #chat-button:hover {
        transition: transform 0.3s ease;
            transform: scale(1.1);
        }
            #chat-logo-button {
            transition: transform 0.3s ease;
            transform: rotate(0deg);
        }
           #chat-logo-button:hover {
    transition: transform 0.3s ease;
    transform: scale(.95) rotate(10deg); /* Combine both transformations */
}

        @keyframes slideIn {
    from {
        opacity: 0;
        transform: translateX(100%);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes slideOut {
    from {
        opacity: 1;
        transform: translateX(0);
    }
    to {
        opacity: 0;
        transform: translateX(100%);
    }
}

        

        #chat-widget #chat-widget .page::-webkit-scrollbar {
            width: 8px;
        }

        #chat-widget #chat-widget .page::-webkit-scrollbar-track {
            background:rgb(255, 255, 255);
            border-radius: 10px;
        }

        #chat-widget #chat-widget .page::-webkit-scrollbar-thumb {
            background-color: #85c1ad;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }

        #chat-widget #chat-widget .page::-webkit-scrollbar-thumb:hover {
            background-color: #85c1ad;
        }

        #chat-messages::-webkit-scrollbar {
            width: 8px;
        }

        #chat-messages::-webkit-scrollbar-track {
            background:rgb(255, 255, 255);
            border-radius: 10px;
        }

        #chat-messages::-webkit-scrollbar-thumb {
            background-color: #85c1ad;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }

        #chat-messages::-webkit-scrollbar-thumb:hover {
            background-color: #85c1ad;
        }

    #minimize-chat {
    background: transparent;
    border: none;
    color: #fff;
    font-size: 20px;
    cursor: pointer;
    padding: 10px;
    border-radius: 50%;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
}

#minimize-chat::before {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    width: 0;
    height: 0;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 50%;
    transform: translate(-50%, -50%);
    transition: width 0.3s ease, height 0.3s ease;
}

#minimize-chat:hover::before {
    width: 100%;
    height: 100%;
}

#minimize-chat i {
    transition: transform 0.3s ease, color 0.3s ease;
}

#minimize-chat:hover i {
    transform: translateY(2px); /* Move the icon down slightly on hover */
    color: rgba(255, 255, 255, 0.8); /* Slightly fade the icon color */
}

        .card img, .card iframe {
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 15px;
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
            text-align: center;
        }
        
        .message-image-container img {
            max-width: 100%;
            border-radius: 8px;
            height: auto;
            display: block;
            margin: 0 auto;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s ease;
        }

        .message-image-container img:hover {
            transform: scale(1.05);
        }
        
        .bot-message img {
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        
        .bot-message img:hover {
            transform: scale(1.05);
        }

        .lead-form {
            padding: 15px;
            margin-bottom: 10px;
        }
        
        .lead-input {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            border: 2px solid #85c1ad;
            border-radius: 30px;
        }
        
        .lead-submit-btn {
            background-color: #85c1ad;
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 30px;
            cursor: pointer;
        }
        
        .lead-submit-btn:hover {
            opacity: 0.9;
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
                bottom: 10px !important; /* Adjust this value for mobile view */
                left: unset;
                right: 0px !important;    
   
            }
            #text-slides-container {
                width: 0px;
            }
            #chat-widget #chat-widget .message {
                max-width: 80%;
            }
        }

        /* New CSS for multi-page layout */
        #chat-widget #chat-widget .page {
                z-index: -1;
            height: calc(100%); /* Subtract footer height */
    overflow-y: auto;
    position: relative;
    display: none;
        }

        .page.active {
            display: block;
        }

       #chat-footer {
    display: flex;
    justify-content: space-around;
    align-items: center;
    padding: 0px;
    background-color: #fff;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
    position: sticky;
    bottom: 0;
    z-index: 9;
}

.footer-button {
    position: relative;
    display: flex;
    gap: 25px;
    margin: 0;
    padding: 0;
    list-style: none;
}

.footer-button li {
    position: relative;
    list-style: none;
    width: 50px;
    height: 50px;
    background:rgba(255, 255, 255, 0);
    border-radius: 50px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    transition: 0.2s;
}

.footer-button li:hover {
    width: 100px;
}

.footer-button li::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 50px;
    background: linear-gradient(45deg, var(--i), var(--j));
    opacity: 0;
    transition: 0.2s;
}

.footer-button li:hover::before {
    opacity: 1;
}

.footer-button li::after {
    content: "";
    position: absolute;
    top: 10px;
    width: 100%;
    height: 100%;
    border-radius: 50px;
    transition: 0.2s;
    filter: blur(15px);
    z-index: -1;
    opacity: 0;
}

.footer-button li:hover::after {
    opacity: 0.5;
}

.footer-button li .icon {
    color: #85c1ad;
    font-size: 1.5em;
    transition: 0.2s;
    transition-delay: 0.25s;
}

.footer-button li:hover .icon {
    transform: scale(0);
    color: #fff;
    transition-delay: 0s;
}

.footer-button li span {
    position: absolute;
}

.footer-button li .title {
    color: #fff;
    font-size: 1em;
    font-family: "Nunito", sans-serif;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    transform: scale(0);
    transition: 0.2s;
    transition-delay: 0s;
}

.footer-button li:hover .title {
    transform: scale(1);
    transition-delay: 0.10s;
}



        .footer-button {
    background: none;
    border: none;
    color: #0b3d2c;
    font-size: 14px;
    cursor: pointer;
    padding: 5px 10px;
    transition: all 0.2s ease;
    position: relative; /* Required for the glow effect */
    overflow: hidden; /* Hide overflow for the glow effect */
}
    .footer-button:hover {
    color: #85c1ad;
}

#chat-widget:has(#chat-page.active) .wave,
#chat-widget:has(#help-page.active) .wave {
    display: none;
}


        .footer-button.active {
            color: #85c1ad;
            font-weight: bold;
        }

        #home-page {
    padding: 10px;
    background-image: url('https://github.com/vibhurj/pictures/blob/main/rb_4722555.png?raw=true'); /* Replace with your image URL */
    background-size: 500px 100%;
    background-position: right; /* Center the image */
    background-repeat: no-repeat; /* Prevent the image from repeating */
    background-attachment: fixed; /* This keeps the background fixed while scrolling */
}

        .welcome-message h1{
        font-family: "Nunito", sans-serif;
            margin-top: 75px;
    font-size: 40px;
        font-weight: 800;
    color:#85c1ad;
    margin-bottom: 5px;
        }
    .welcome-message h3{
    font-family: "Nunito", sans-serif;
        font-weight: 600;
    font-size: 25px;
    color:#85c1ad;
    margin-bottom: 25px;
        }

        .quick-links {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .quick-link {
width: 50%;
display: flex;
justify-content: space-between;
font-family: "Nunito", sans-serif;
font-weight:600;
  position: relative;
  padding: 10px 22px;
  border-radius: 20px;
  border: none;
  color: white;
  cursor: pointer;
  background-color: #85c1ad;
  transition: all 0.2s ease;
}

.quick-link:hover {
transform: scale(0.97);
  transition: all 0.2s ease;
}


.quick-link:before,
.quick-link:after {
  position: absolute;
  content: "";
  width: 150%;
  left: 50%;
  height: 100%;
  transform: translateX(-50%);
  z-index: -1000;
  background-repeat: no-repeat;
}

.quick-link:hover:before {
  top: -70%;
  background-image: radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, transparent 20%, #85c1ad; 20%, transparent 30%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, transparent 10%, #85c1ad; 15%, transparent 20%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%),
    radial-gradient(circle, #85c1ad; 20%, transparent 20%);
  background-size: 10% 10%, 20% 20%, 15% 15%, 20% 20%, 18% 18%, 10% 10%, 15% 15%,
    10% 10%, 18% 18%;
  background-position: 50% 120%;
  animation: greentopBubbles 0.6s ease;
}

@keyframes greentopBubbles {
  0% {
    background-position: 5% 90%, 10% 90%, 10% 90%, 15% 90%, 25% 90%, 25% 90%,
      40% 90%, 55% 90%, 70% 90%;
  }

  50% {
    background-position: 0% 80%, 0% 20%, 10% 40%, 20% 0%, 30% 30%, 22% 50%,
      50% 50%, 65% 20%, 90% 30%;
  }

  100% {
    background-position: 0% 70%, 0% 10%, 10% 30%, 20% -10%, 30% 20%, 22% 40%,
      50% 40%, 65% 10%, 90% 20%;
    background-size: 0% 0%, 0% 0%, 0% 0%, 0% 0%, 0% 0%;
  }
}

.quick-link:hover::after {
  bottom: -70%;
  background-image: radial-gradient(circle, #85c1ad 20%, transparent 20%),
    radial-gradient(circle, #85c1ad 20%, transparent 20%),
    radial-gradient(circle, transparent 10%, #85c1ad 15%, transparent 20%),
    radial-gradient(circle, #85c1ad 20%, transparent 20%),
    radial-gradient(circle, #85c1ad 20%, transparent 20%),
    radial-gradient(circle, #85c1ad 20%, transparent 20%),
    radial-gradient(circle, #85c1ad 20%, transparent 20%);
  background-size: 15% 15%, 20% 20%, 18% 18%, 20% 20%, 15% 15%, 20% 20%, 18% 18%;
  background-position: 50% 0%;
  animation: greenbottomBubbles 0.6s ease;
}

@keyframes greenbottomBubbles {
  0% {
    background-position: 10% -10%, 30% 10%, 55% -10%, 70% -10%, 85% -10%,
      70% -10%, 70% 0%;
  }

  50% {
    background-position: 0% 80%, 20% 80%, 45% 60%, 60% 100%, 75% 70%, 95% 60%,
      105% 0%;
  }

  100% {
    background-position: 0% 90%, 20% 90%, 45% 70%, 60% 110%, 75% 80%, 95% 70%,
      110% 10%;
    background-size: 0% 0%, 0% 0%, 0% 0%, 0% 0%;
  }
}

        .quick-access-buttons {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-top: 15px;
}
.quick-access-buttons div{
    display: flex;
    gap: 10px;
}

/* From Uiverse.io by Mhyar-nsi */ 
.quick-access-button {
    width: 100%;
    font-family: "Nunito", sans-serif;
    font-weight:600;
    box-shadow: 2px 2px 10pxrgba(0, 0, 0, 0.09);
    border: 0.5px solid #85c1ad;
    background-color: #ffffff;
    color:#85c1ad;
    cursor: pointer;
    border-radius: 20px;
    height: 40px;
    transition: 0.3s;
}

.quick-access-button:hover {
  background-color: #85c1ad;
  box-shadow: 0 0 0 2px #85c1ad;
  color: #fff;
}



    
        .quick-link svg{
        color:rgb(255, 255, 255);
        }
        #help-page {
            padding: 20px;
            overflow-y: auto;
        }

        .help-section {
            margin-bottom: 20px;
        }

        .help-section h3 {
            color: #0b3d2c;
            margin-bottom: 10px;
        }

        .help-section p {
            color: #343a40;
            line-height: 1.5;
        }

        /* Text slide-in/slide-out animation */
        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(100%);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        @keyframes slideOut {
    from {
        opacity: 1;
        transform: translateX(0);
    }
    to {
        opacity: 0;
        transform: translateX(-100%);
    }
}

#text-slides-container div.slide-out {
    animation: slideOut 0.5s ease forwards;
}

        #text-slides-container {
            width: 0px;
            height: 0px;
            margin-bottom: 10px;
            margin-right: 0px;
            padding-right: 5px;
            transition: all 0.3s ease;
            z-index: 998;
            overflow: hidden;
            position: relative;
            text-align: right;
            color: #85c1ad;
            font-weight: bold;
            font-size: 16px;
            border-radius: 10px;
            padding: 10px;
        }

        #text-slides-container {
    width: 150px;
    height: 80px;
    margin-bottom: 10px;
    margin-right: 0px;
    padding-right: 5px;
    transition: all 0.3s ease;
    z-index: 998;
    overflow: hidden;
    position: relative;
    text-align: right;
    color: #85c1ad;
    font-weight: bold;
    font-size: 16px;
    border-radius: 10px;
    padding: 10px;
}

#text-slides-container div {
    position: absolute;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0;
    transform: translateX(100%);
    animation: slideIn 0.5s ease forwards;
}

#text-slides-container div.slide-out {
    animation: slideOut 0.5s ease forwards;
}
            .section1{
            position: relative;
            width: 100%;
            height: 220px;
            margin-top: 20px;
            border-radius: 25px;
            }

            .message.bot-message.first-bot-message {
    max-width: 0% !important; /* Override default width */
    width: 0% !important;
    float: none; /* Remove float to ensure full width */
    clear: both;
    margin-bottom:10px; /* Remove any default margins */
    padding: 20px; /* Add padding for better spacing */
    border-radius: 10px; /* Optional: Add rounded corners */
    background-color: #f8f9fa; /* Optional: Add a background color */
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1); /* Optional: Add a subtle shadow */
}
    .message.bot-message.first-bot-message h3{
    font-size:24px;
}

/* From Uiverse.io by alexruix */ 
/* From uiverse.io by @alexruix */
#chat-input .input {
width: 75%;
 line-height: 28px;
 border: 2px solid transparent;
 border-bottom-color: #777;
 padding: .2rem 0;
 outline: none;
 background-color: transparent;
 color: #0d0c22;
 transition: .3s cubic-bezier(0.645, 0.045, 0.355, 1);
}

#chat-input .input:focus, #chat-input .input:hover {
 outline: none;
 padding: .2rem 1rem;
 border-radius: 1rem;
 border-color:#85c1ad;
}

#chat-input .input::placeholder {
 color: #777;
}

#chat-input .input:focus::placeholder {
 opacity: 0;
 transition: opacity .3s;
}


/* From Uiverse.io by Smit-Prajapati */ 
.parent {
position: absolute;
width:100%;
height:100%;
  perspective: 1000px;
}

.card {
width:100%;
  height: 100%;
  border-radius: 55px;
  background: linear-gradient(135deg, #85c1ad, #85c1ad);
  transition: all 0.5s ease-in-out;
  transform-style: preserve-3d;
  box-shadow: rgba(5, 71, 17, 0) 40px 50px 25px -40px, rgba(5, 71, 17, 0.2) 0px 25px 25px -5px;
}

.glass {
  transform-style: preserve-3d;
  position: absolute;
  inset: 8px;
  border-radius: 55px;
  border-top-right-radius: 100%;
  background: linear-gradient(0deg, rgba(255, 255, 255, 0.349) 0%, rgba(255, 255, 255, 0.815) 100%);
  /* -webkit-backdrop-filter: blur(5px);
  backdrop-filter: blur(5px); */
  transform: translate3d(0px, 0px, 25px);
  border-left: 1px solid white;
  border-bottom: 1px solid white;
  transition: all 0.5s ease-in-out;
}

.content {
  padding: 10px 60px 0px 30px;
  transform: translate3d(0, 0, 26px);
}

.content .title {
  display: block;
  color: #85c1ad;
  font-weight: 900;
  font-size: 20px;
}

.content .text {
  display: block;
  color: #85c1ad;
  font-size: 15px;
  margin-top: 20px;
}

.bottom {
  padding: 10px 12px;
  transform-style: preserve-3d;
  position: absolute;
  bottom: 20px;
  left: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transform: translate3d(0, 0, 26px);
}

.bottom .view-more {
  display: flex;
  align-items: center;
  width: 40%;
  justify-content: flex-end;
  transition: all 0.2s ease-in-out;
}

.bottom .view-more:hover {
  transform: translate3d(0, 0, 10px);
}

.bottom .view-more .view-more-button {
  background: none;
  border: none;
  color: #85c1ad;
  font-weight: bolder;
  font-size: 12px;
}

.bottom .view-more .svg {
  fill: none;
  stroke: #00c37b;
  stroke-width: 3px;
  max-height: 15px;
}

.bottom .social-buttons-container {
  display: flex;
  gap: 10px;
  transform-style: preserve-3d;
}

.bottom .social-buttons-container .social-button {
  width: 30px;
  aspect-ratio: 1;
  padding: 5px;
  background: rgb(255, 255, 255);
  border-radius: 50%;
  border: none;
  display: grid;
  place-content: center;
  box-shadow: rgba(5, 71, 17, 0.5) 0px 7px 5px -5px;
}

.bottom .social-buttons-container .social-button:first-child {
  transition: transform 0.2s ease-in-out 0.4s, box-shadow 0.2s ease-in-out 0.4s;
}

.bottom .social-buttons-container .social-button:nth-child(2) {
  transition: transform 0.2s ease-in-out 0.6s, box-shadow 0.2s ease-in-out 0.6s;
}

.bottom .social-buttons-container .social-button:nth-child(3) {
  transition: transform 0.2s ease-in-out 0.8s, box-shadow 0.2s ease-in-out 0.8s;
}

.logo {
  position: absolute;
  right: 0;
  top: 0;
  transform-style: preserve-3d;
}

.logo .circle {
  display: block;
  position: absolute;
  aspect-ratio: 1;
  border-radius: 50%;
  top: 0;
  right: 0;
  box-shadow: rgba(100, 100, 111, 0.2) -10px 10px 20px 0px;
  -webkit-backdrop-filter: blur(5px);
  backdrop-filter: blur(3px);
  background:rgba(255, 255, 255, 0.07);
  transition: all 0.5s ease-in-out;
}

.logo .circle1 {
  width: 170px;
  transform: translate3d(0, 0, 20px);
  top: 8px;
  right: 8px;
}

.logo .circle2 {
  width: 140px;
  transform: translate3d(0, 0, 40px);
  top: 10px;
  right: 10px;
  -webkit-backdrop-filter: blur(1px);
  backdrop-filter: blur(1px);
  transition-delay: 0.4s;
}

.logo .circle3 {
  width: 110px;
  transform: translate3d(0, 0, 60px);
  top: 17px;
  right: 17px;
  transition-delay: 0.8s;
}

.logo .circle4 {
  width: 80px;
  transform: translate3d(0, 0, 80px);
  top: 23px;
  right: 23px;
  transition-delay: 1.2s;
}

.logo .circle5 {
  width: 50px;
  transform: translate3d(0, 0, 100px);
  top: 30px;
  right: 30px;
  display: grid;
  place-content: center;
  transition-delay: 1.6s;
}

.logo .circle5 .svg {
  width: 20px;
  fill: white;
}

.parent:hover .card {
  transform: rotate3d(1, 1, 0, 20deg);
  box-shadow: rgba(5, 71, 17, 0.3) 30px 50px 25px -40px, rgba(5, 71, 17, 0.1) 0px 25px 30px 0px;
}

.parent:hover .card .bottom .social-buttons-container .social-button {
  transform: translate3d(0, 0, 50px);
  box-shadow: rgba(5, 71, 17, 0.2) -5px 20px 10px 0px;
}

.parent:hover .card .logo .circle2 {
  transform: translate3d(0, 0, 60px);
}

.parent:hover .card .logo .circle3 {
  transform: translate3d(0, 0, 80px);
}

.parent:hover .card .logo .circle4 {
  transform: translate3d(0, 0, 100px);
}

.parent:hover .card .logo .circle5 {
  transform: translate3d(0, 0, 120px);
}

#chat-logo-button::after{
position: absolute;
z-index: 1000000;
top: 0;
left: 0;
width:30px;
height:30px;
background-color:green;
border-radius:50%;

}

.online-dot {
    position: absolute;
    top: -3px;
    left: 5px;
    width: 15px;
    height: 15px;
    background-color: #3ac740;
    box-shadow: 0px 3px 8px #00000038;
    border-radius: 50%;
    border: 2px solid #fff;
    z-index: 1002;
}

/* From Uiverse.io by DevPTG */ 
#load {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 40%;
  overflow: visible;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  user-select: none;
  cursor: default;
}

#load div {
  position: absolute;
  width: 20px;
  height: 36px;
  opacity: 0;
  font-family: Helvetica, Arial, sans-serif;
  animation: move 2s linear infinite;
  -o-animation: move 2s linear infinite;
  -moz-animation: move 2s linear infinite;
  -webkit-animation: move 2s linear infinite;
  transform: rotate(180deg);
  -o-transform: rotate(180deg);
  -moz-transform: rotate(180deg);
  -webkit-transform: rotate(180deg);
  color:#85c1ad;
}

#load div:nth-child(2) {
  animation-delay: 0.2s;
  -o-animation-delay: 0.2s;
  -moz-animation-delay: 0.2s;
  -webkit-animation-delay: 0.2s;
}

#load div:nth-child(3) {
  animation-delay: 0.4s;
  -o-animation-delay: 0.4s;
  -webkit-animation-delay: 0.4s;
  -webkit-animation-delay: 0.4s;
}

#load div:nth-child(4) {
  animation-delay: 0.6s;
  -o-animation-delay: 0.6s;
  -moz-animation-delay: 0.6s;
  -webkit-animation-delay: 0.6s;
}

#load div:nth-child(5) {
  animation-delay: 0.8s;
  -o-animation-delay: 0.8s;
  -moz-animation-delay: 0.8s;
  -webkit-animation-delay: 0.8s;
}

#load div:nth-child(6) {
  animation-delay: 1s;
  -o-animation-delay: 1s;
  -moz-animation-delay: 1s;
  -webkit-animation-delay: 1s;
}

#load div:nth-child(7) {
  animation-delay: 1.2s;
  -o-animation-delay: 1.2s;
  -moz-animation-delay: 1.2s;
  -webkit-animation-delay: 1.2s;
}

@keyframes move {
  0% {
    left: 0;
    opacity: 0.1;
  }

  35% {
    left: 41%;
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  65% {
    left: 59%;
    -moz-transform: rotate(0deg);
    -webkit-transform: rotate(0deg);
    -o-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  100% {
    left: 100%;
    -moz-transform: rotate(-180deg);
    -webkit-transform: rotate(-180deg);
    -o-transform: rotate(-180deg);
    transform: rotate(-180deg);
    opacity: 0.1;
  }
}

@-moz-keyframes move {
  0% {
    left: 0;
    opacity: 0.1;
  }

  35% {
    left: 41%;
    -moz-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  65% {
    left: 59%;
    -moz-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  100% {
    left: 100%;
    -moz-transform: rotate(-180deg);
    transform: rotate(-180deg);
    opacity: 0.1;
  }
}

@-webkit-keyframes move {
  0% {
    left: 0;
    opacity: 0.1;
  }

  35% {
    left: 41%;
    -webkit-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  65% {
    left: 59%;
    -webkit-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  100% {
    left: 100%;
    -webkit-transform: rotate(-180deg);
    transform: rotate(-180deg);
    opacity: 0.1;
  }
}

@-o-keyframes move {
  0% {
    left: 0;
    opacity: 0.1;
  }

  35% {
    left: 41%;
    -o-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  65% {
    left: 59%;
    -o-transform: rotate(0deg);
    transform: rotate(0deg);
    opacity: 1;
  }

  100% {
    left: 100%;
    -o-transform: rotate(-180deg);
    transform: rotate(-180deg);
    opacity: 0.1;
  }
}

.option-button {
    padding: 5px 20px;
    margin-top:10px;
    text-transform: uppercase;
    border-radius: 25px;
    font-size: 17px;
    font-weight: 500;
    color:#85c1ad;
    text-shadow: none;
    background: transparent;
    cursor: pointer;
    box-shadow: transparent;
    border: 1px solid #85c1ad;
    transition: 0.2s ease;
    user-select: none;
  }
  
  .option-button:hover,
  .option-button:focus {
    border: 2px solid #85c1ad;
    box-shadow: 2px 2px 7px rgba(108, 117, 125, 0.56);
  }

  .message-input:disabled {
    background-color: #f5f5f5;
    cursor: not-allowed;
}

.send-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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

    // Helper functions
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

    function getCurrentTime() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
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

    function generateSessionId() {
        return str(uuid.uuid4());
    }

    async function fetchActiveFlow() {
        try {
            const response = await fetch(`/api/get-active-flow/${chatbotId}/`);
            const data = await response.json();
            console.log("Fetched flow data:", data);
            if (data.success && data.has_flow) {
                activeFlow = data.flow;
                // Make sure we have a lead_collection_step property (default to last step)
                if (typeof activeFlow.lead_collection_step === 'undefined') {
                    activeFlow.lead_collection_step = activeFlow.steps.length - 1;
                }
                console.log("Active flow set:", activeFlow);
                return true;
            }
            return false;
        } catch (error) {
            console.error('Error fetching active flow:', error);
            return false;
        }
    }

    function initChatWidget() {
        if (document.getElementById('chat-widget')) {
            return;
        }

        const chatButtonContainer = document.createElement('div');
        chatButtonContainer.id = 'chat-button-container';
        chatButtonContainer.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 999;
            transition: all 0.3s ease;
        `;

        // Create text slides container
        const textSlidesContainer = document.createElement('div');
        textSlidesContainer.id = 'text-slides-container';

        const slides = [];
        let currentSlide = 0;

        const slideElement = document.createElement('div');
        slideElement.textContent = slides[currentSlide];
        textSlidesContainer.appendChild(slideElement);

        // Function to cycle through slides with animations
        function cycleSlides() {
            slideElement.classList.add('slide-out');
            
            setTimeout(() => {
                currentSlide = (currentSlide + 1) % slides.length;
                slideElement.textContent = slides[currentSlide];
                
                slideElement.classList.remove('slide-out');
                slideElement.style.animation = 'none';
                void slideElement.offsetWidth;
                slideElement.style.animation = 'slideIn 0.5s ease forwards';
            }, 500);
        }

        // Start the slideshow if there are slides
        if (slides.length > 0) {
            setInterval(cycleSlides, 3000);
        }

        const chatButton = document.createElement('button');
        chatButton.id = 'chat-button';

        const chatToggleUrl = '';
        if (chatToggleUrl && chatToggleUrl !== '#') {
            const toggleImage = document.createElement('img');
            toggleImage.src = chatToggleUrl;
            toggleImage.alt = "Chat Toggle";
            toggleImage.style.width = '100%';
            toggleImage.style.height = '100%';
            toggleImage.style.objectFit = 'cover';
            toggleImage.style.borderRadius = '50%';
            chatButton.appendChild(toggleImage);
        } else {
            chatButton.innerHTML = '<div class="online-dot"></div><img id="chat-logo-button" src="https://github.com/vibhurj/pictures/blob/main/chatbot.png?raw=true" height="35">';
        }

        // Append components to containers
        chatButtonContainer.appendChild(textSlidesContainer);
        chatButtonContainer.appendChild(chatButton);

        const chatWidget = document.createElement('div');
        chatWidget.id = 'chat-widget';

        chatWidget.innerHTML = `
            <div id="chat-header">
                <div class="header-text-container">
                    <img id="chat-logo" src="${'' || '#'}" alt="Chatbot Logo">
                    <div data-original-text="Chat">Chat</div>
                </div>
                <button id="minimize-chat">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </div>
            <svg class="wave" viewBox="0 0 500 50" preserveAspectRatio="none">
                <defs>
                    <linearGradient id="waveGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" style="stop-color:#9111d2;stop-opacity:1" />
                        <stop offset="50%" style="stop-color:#9111d2;stop-opacity:1" />
                    </linearGradient>
                </defs>
                <path
                    class="wave-path"
                    d="M0,20 C150,50 350,0 500,20 L500,50 L0,50 Z"
                    style="stroke: none; fill: #85c1ad;"
                ></path>
            </svg>
            <div id="home-page" class="page">
                <div class="welcome-message">
                    <h1>Welcome !</h1> 
                    <h3>How can we assist you today?</h3>
                </div>
                <div class="quick-links">
                    <div class="quick-link" onclick="window.navigateToPage('chat')">Start Chat <span><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="currentColor" class="bi bi-chat-left-text" viewBox="0 0 16 16">
                    <path d="M14 1a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4.414A2 2 0 0 0 3 11.586l-2 2V2a1 1 0 0 1 1-1zM2 0a2 2 0 0 0-2 2v12.793a.5.5 0 0 0 .854.353l2.853-2.853A1 1 0 0 1 4.414 12H14a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2z"/>
                    <path d="M3 3.5a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5M3 6a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9A.5.5 0 0 1 3 6m0 2.5a.5.5 0 0 1 .5-.5h5a.5.5 0 0 1 0 1h-5a.5.5 0 0 1-.5-.5"/>
                    </svg></span></div>
                    <div class="quick-link" onclick="window.navigateToPage('help')">Get Help <span><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" fill="currentColor" class="bi bi-question-lg" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M4.475 5.458c-.284 0-.514-.237-.47-.517C4.28 3.24 5.576 2 7.825 2c2.25 0 3.767 1.36 3.767 3.215 0 1.344-.665 2.288-1.79 2.973-1.1.659-1.414 1.118-1.414 2.01v.03a.5.5 0 0 1-.5.5h-.77a.5.5 0 0 1-.5-.495l-.003-.2c-.043-1.221.477-2.001 1.645-2.712 1.03-.632 1.397-1.135 1.397-2.028 0-.979-.758-1.698-1.926-1.698-1.009 0-1.71.529-1.938 1.402-.066.254-.278.461-.54.461h-.777ZM7.496 14c.622 0 1.095-.474 1.095-1.09 0-.618-.473-1.092-1.095-1.092-.606 0-1.087.474-1.087 1.091S6.89 14 7.496 14"/>
                    </svg></span></div>
                </div>
                <div class="section1">
                    <div class="parent">
                        <div class="card">
                            <div class="logo">
                                <span class="circle circle1"></span>
                                <span class="circle circle2"></span>
                                <span class="circle circle3"></span>
                                <span class="circle circle4"></span>
                                <span class="circle circle5">
                                    <img src="${'' || '#'}" alt="Chatbot Logo" height="35">
                                </span>
                            </div>
                            <div class="glass"></div>
                            <div class="content">
                                <span class="title">Chat</span>
                                <span class="text">Business Information</span>
                            </div>
                            <div class="bottom">
                                <div class="social-buttons-container">
                                    <button class="social-button .social-button1">
                                        <svg viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg" class="svg">
                                            <path d="M 9.9980469 3 C 6.1390469 3 3 6.1419531 3 10.001953 L 3 20.001953 C 3 23.860953 6.1419531 27 10.001953 27 L 20.001953 27 C 23.860953 27 27 23.858047 27 19.998047 L 27 9.9980469 C 27 6.1390469 23.858047 3 19.998047 3 L 9.9980469 3 z M 22 7 C 22.552 7 23 7.448 23 8 C 23 8.552 22.552 9 22 9 C 21.448 9 21 8.552 21 8 C 21 7.448 21.448 7 22 7 z M 15 9 C 18.309 9 21 11.691 21 15 C 21 18.309 18.309 21 15 21 C 11.691 21 9 18.309 9 15 C 9 11.691 11.691 9 15 9 z M 15 11 A 4 4 0 0 0 11 15 A 4 4 0 0 0 15 19 A 4 4 0 0 0 19 15 A 4 4 0 0 0 15 11 z"></path>
                                        </svg>
                                    </button>
                                    <button class="social-button .social-button2">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="svg" viewBox="0 0 16 16">
                                            <path d="M12.6.75h2.454l-5.36 6.142L16 15.25h-4.937l-3.867-5.07-4.425 5.07H.316l5.733-6.57L0 .75h5.063l3.495 4.633L12.601.75Zm-.86 13.028h1.36L4.323 2.145H2.865z"/>
                                        </svg>
                                    </button>
                                    <button class="social-button .social-button3">
                                        <svg xmlns="http://www.w3.org/2000/svg" class="svg" viewBox="0 0 16 16">
                                            <path d="M16 8.049c0-4.446-3.582-8.05-8-8.05C3.58 0-.002 3.603-.002 8.05c0 4.017 2.926 7.347 6.75 7.951v-5.625h-2.03V8.05H6.75V6.275c0-2.017 1.195-3.131 3.022-3.131.876 0 1.791.157 1.791.157v1.98h-1.009c-.993 0-1.303.621-1.303 1.258v1.51h2.218l-.354 2.326H9.25V16c3.824-.604 6.75-3.934 6.75-7.951"/>
                                        </svg>
                                    </button>
                                </div>
                                <div class="view-more">
                                    <button class="view-more-button">View more</button>
                                    <svg class="svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div id="chat-page" class="page active">
                <div id="chat-messages">
                    <div id="carousel-container">
                        <div id="carousel">
                            <!-- Carousel items will be dynamically added here -->
                        </div>
                    </div>
                    <div id="buttons">
                        <!-- Buttons will be dynamically added here -->
                    </div>
                </div>
                <div id="chat-input">
                    <input class="input" type="text" id="message" placeholder="Type a message..." data-original-placeholder="Type a message...">
                    <button id="mic-button"><i class="fas fa-microphone"></i></button>
                    <button id="send-button"><i class="fas fa-paper-plane"></i></button>
                </div>
                <div id="translation-disclaimer">
                    Note: Automated translations may not be completely accurate. Please refer to English text for precise communication.
                </div>
            </div>
            <div id="help-page" class="page">
                <div class="help-section">
                    <h3>How to Use the Chatbot</h3>
                    <p>1. Click on the "Start Chat" button to begin a conversation.</p>
                    <p>2. Type your message in the input box and press Enter or click the send button.</p>
                    <p>3. Use the microphone button to speak your message.</p>
                </div>
                <div class="help-section">
                    <h3>FAQs</h3>
                    <p><strong><p>FAQ</p></strong></p>
                </div>
            </div>
            <div id="chat-footer">
                <ul class="footer-button">
                    <li style="--i:#85c1ad;--j:#85c1ad;" onclick="window.navigateToPage('home')">
                        <span class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="27" height="27" fill="currentColor" class="bi bi-house-door-fill" viewBox="0 0 16 16">
                        <path d="M6.5 14.5v-3.505c0-.245.25-.495.5-.495h2c.25 0 .5.25.5.5v3.5a.5.5 0 0 0 .5.5h4a.5.5 0 0 0 .5-.5v-7a.5.5 0 0 0-.146-.354L13 5.793V2.5a.5.5 0 0 0-.5-.5h-1a.5.5 0 0 0-.5.5v1.293L8.354 1.146a.5.5 0 0 0-.708 0l-6 6A.5.5 0 0 0 1.5 7.5v7a.5.5 0 0 0 .5.5h4a.5.5 0 0 0 .5-.5"/>
                        </svg></span>
                        <span class="title">Home</span>
                    </li>
                </ul>
                <ul class="footer-button">
                    <li style="--i:#85c1ad;--j:#85c1ad;" onclick="window.navigateToPage('chat')">
                        <span class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="27" height="27" fill="currentColor" class="bi bi-chat-square-dots-fill" viewBox="0 0 16 16">
                        <path d="M0 2a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.5a1 1 0 0 0-.8.4l-1.9 2.533a1 1 0 0 1-1.6 0L5.3 12.4a1 1 0 0 0-.8-.4H2a2 2 0 0 1-2-2zm5 4a1 1 0 1 0-2 0 1 1 0 0 0 2 0m4 0a1 1 0 1 0-2 0 1 1 0 0 0 2 0m3 1a1 1 0 1 0 0-2 1 1 0 0 0 0 2"/>
                        </svg></span>
                        <span class="title">Chat</span>
                    </li>
                </ul>
                <ul class="footer-button">
                    <li style="--i:#85c1ad;--j:#85c1ad;" onclick="window.navigateToPage('help')">
                        <span class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="27" height="27" fill="currentColor" class="bi bi-patch-question-fill" viewBox="0 0 16 16">
                        <path d="M5.933.87a2.89 2.89 0 0 1 4.134 0l.622.638.89-.011a2.89 2.89 0 0 1 2.924 2.924l-.01.89.636.622a2.89 2.89 0 0 1 0 4.134l-.637.622.011.89a2.89 2.89 0 0 1-2.924 2.924l-.89-.01-.622.636a2.89 2.89 0 0 1-4.134 0l-.622-.637-.89.011a2.89 2.89 0 0 1-2.924-2.924l.01-.89-.636-.622a2.89 2.89 0 0 1 0-4.134l.637-.622-.011-.89a2.89 2.89 0 0 1 2.924-2.924l.89.01zM7.002 11a1 1 0 1 0 2 0 1 1 0 0 0-2 0m1.602-2.027c.04-.534.198-.815.846-1.26.674-.475 1.05-1.09 1.05-1.986 0-1.325-.92-2.227-2.262-2.227-1.02 0-1.792.492-2.1 1.29A1.7 1.7 0 0 0 6 5.48c0 .393.203.64.545.64.272 0 .455-.147.564-.51.158-.592.525-.915 1.074-.915.61 0 1.03.446 1.03 1.084 0 .563-.208.885-.822 1.325-.619.433-.926.914-.926 1.64v.111c0 .428.208.745.585.745.336 0 .504-.24.554-.627"/>
                        </svg></span>
                        <span class="title">Help</span>
                    </li>
                </ul>
            </div>
        `;

        document.body.appendChild(chatButtonContainer);
        document.body.appendChild(chatWidget);

        // Expose navigateToPage to the global scope
        window.navigateToPage = function(page) {
            const pages = document.querySelectorAll('.page');
            pages.forEach(p => p.classList.remove('active'));

            const buttons = document.querySelectorAll('.footer-button');
            buttons.forEach(b => b.classList.remove('active'));

            document.getElementById(`${page}-page`).classList.add('active');
            document.querySelector(`.footer-button[onclick="window.navigateToPage('${page}')"]`).classList.add('active');

            const wave = document.querySelector('.wave');
            if (page === 'chat' || page === 'help') {
                wave.style.display = 'none'; // Hide the wave on chat and help pages
            } else {
                wave.style.display = 'block'; // Show the wave on other pages
            }
        };

        // Add event listeners
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

        // Initialize carousel
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

        // Adjust widget for mobile
        adjustWidgetForMobile();
        window.addEventListener('resize', adjustWidgetForMobile);

        // Set up MutationObserver
        const chatMessages = document.getElementById('chat-messages');
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.addedNodes.length) {
                    mutation.addedNodes.forEach((node) => {
                        if (node.classList && node.classList.contains('button-container')) {
                            console.log("New button container detected");
                            initializeButtonHandlers();
                        }
                    });
                }
            });
        });
        
        observer.observe(chatMessages, { childList: true, subtree: true });
        
        // Set widget as initialized
        widgetInitialized = true;
    }

    function toggleChat() {
        var chatWidget = document.getElementById('chat-widget');
        var chatButtonContainer = document.getElementById('chat-button-container');
    
        if (chatWidget.style.display === 'none' || chatWidget.style.display === '') {
            console.log("Opening chat widget - Active flow:", activeFlow);
            chatWidget.style.display = 'flex';
            chatButtonContainer.style.display = 'none';
            chatWidget.style.animation = 'slideIn 0.3s ease-out';
    
            // Clear previous chat
            document.getElementById('chat-messages').innerHTML = '';
    
            // Reset state when the chat is opened
            userMessageCount = 0;
            currentStep = 0;
            leadState = {
                nameCollected: false,
                phoneCollected: false,
                name: '',
                phone: '',
                userId: null
            };
    
            // Start custom flow if available, otherwise use default welcome message
            if (activeFlow && activeFlow.steps && activeFlow.steps.length > 0) {
                console.log("Starting custom flow with steps:", activeFlow.steps);
                processFlowStep(0);
            } else {
                console.log("No active flow, using default welcome message");
                // Add welcome message
                appendMessage("Welcome! How may I help you?", 'bot-message');
                
                // IMPORTANT FIX: Check if we should collect leads immediately 
                // when there's no active flow
                if (leadsEnabled && !leadState.nameCollected) {
                    setTimeout(() => {
                        handleLeadCollection();
                    }, 1000);
                }
            }
    
            // Update input state based on lead collection status
            updateInputState();
    
            fetch('http://127.0.0.1:8000/chat/response/12/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    query: "hello",
                    session_id: null,
                    is_new_session: true,
                    chatbot_id: chatbotId,
                    logo_url: ''
                })
            })
            .then(response => response.json())
            .then(data => {
                sessionId = data.session_id;
                chatbotId = data.chatbot_id;
            })
            .catch(error => {
                console.error('Error initializing chat session:', error);
                // Add error handling - still show widget even if request fails
                appendMessage("I'm ready to chat! How can I help you today?", 'bot-message');
            });
        } else {
            chatWidget.style.animation = 'slideIn 0.3s ease-out reverse';
            setTimeout(() => {
                chatWidget.style.display = 'none';
                chatButtonContainer.style.display = 'flex';
            }, 300);
        }
    
        adjustWidgetForMobile();
    }
    
    function adjustWidgetForMobile() {
        const chatWidget = document.getElementById('chat-widget');
        const chatButtonContainer = document.getElementById('chat-button-container');

        if (!chatWidget || !chatButtonContainer) {
            console.log("Required elements not found for mobile adjustment");
            return;
        }

        if (window.innerWidth <= 768) {
            chatWidget.style.width = '100%';
            chatWidget.style.height = '100%';
            chatWidget.style.bottom = '0';
            chatWidget.style.right = '0';
            chatWidget.style.borderRadius = '0';
        } else {
            chatWidget.style.width = '420px';
            chatWidget.style.height = '720px';
            chatWidget.style.bottom = '20px';
            chatWidget.style.right = '20px';
            chatWidget.style.borderRadius = '35px';

            chatButtonContainer.style.bottom = '40px';
            chatButtonContainer.style.right = '50px';
        }
    }

    // Message handling functions
    function appendMessage(content, className, isHTML = false) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) {
            console.error("Chat messages container not found");
            return;
        }

        const messageContainer = document.createElement('div');
        messageContainer.classList.add('message-container');
    
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', className);
    
        // Handle content (HTML or text)
        if (isHTML) {
            messageDiv.innerHTML = content;
        } else {
            // Split content by newline and create paragraphs
            const paragraphs = content.split('\n');
            paragraphs.forEach(paragraph => {
                if (paragraph.trim()) {
                    const p = document.createElement('p');
                    p.setAttribute('data-original-text', paragraph);
                    p.innerHTML = formatMessage(paragraph, className === 'bot-message');
                    messageDiv.appendChild(p);
                }
            });
        }
    
        // Add timestamp
        const timestampDiv = document.createElement('div');
        timestampDiv.classList.add('timestamp');
        timestampDiv.textContent = getCurrentTime();
        messageDiv.appendChild(timestampDiv);
    
        // Append message and scroll to bottom
        messageContainer.appendChild(messageDiv);
        chatMessages.appendChild(messageContainer);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    
        // Initialize button handlers if needed
        if (isHTML && content.includes('option-button')) {
            setTimeout(() => initializeButtonHandlers(), 100);
        }
    
        // Track user messages
        if (className === 'user-message') {
            userMessageCount++;
            console.log(`User message count: ${userMessageCount}`);
            
            // Check if we should trigger lead collection
            if (userMessageCount >= 3 && !leadState.nameCollected && leadsEnabled) {
                console.log("Third user message detected - triggering lead collection");
                setTimeout(() => {
                    handleLeadCollection();
                }, 800);
            }
        }
    }

    function formatMessage(message, isBot) {
        if (isBot) {
            // Convert image markdown to HTML
            message = message.replace(/!\[(.*?)\]\((.*?)\)/g, (match, alt, url) => {
                return `<div class="message-image-container">
                    <img src="${url}" alt="${alt || 'Image'}" style="max-width: 200px; height: auto;"/>
                </div>`;
            });
    
            // Remove empty lines
            message = message.replace(/^\s*[\r\n]/gm, '');
    
            // Process remaining markdown
            return marked ? marked.parse(message) : message;
        } else {
            // Handle user messages (e.g., URLs and line breaks)
            return message
                .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
                .replace(/\n/g, '<br>');
        }
    }

    function updateInputState() {
        const messageInput = document.getElementById('message');
        const sendButton = document.getElementById('send-button');
        
        if (!messageInput || !sendButton) return;
        
        // Disable input if leads are required but not collected
        if (leadsEnabled && (!leadState.nameCollected || !leadState.phoneCollected)) {
            messageInput.disabled = true;
            sendButton.disabled = true;
            messageInput.placeholder = 'Please complete the form...';
        } else {
            messageInput.disabled = false;
            sendButton.disabled = false;
            messageInput.placeholder = 'Type a message...';
        }
    }

    function sendMessage() {
        var messageInput = document.getElementById('message');
        if (!messageInput) return;
        
        var message = messageInput.value.trim();
        if (message === '') return;
    
        // Show user message
        appendMessage(message, 'user-message');
        messageInput.value = '';
    
        // IMPORTANT FIX: Check for lead collection before sending message
        if (leadsEnabled && (!leadState.nameCollected || !leadState.phoneCollected)) {
            if (handleLeadCollection()) {
                return;
            }
        }
    
        // Create loading message
        var loadingDiv = document.createElement('div');
        loadingDiv.classList.add('message', 'bot-message');
        loadingDiv.innerHTML = `
            <div style="display: flex; flex-direction: column; background-color: rgb(255, 255, 255); width: 284px; height: 256px; border-radius: 12px; padding: 16px; gap: 16px;">
                <div style="overflow:hidden; position:relative; display: flex; justify-content:center; align-items:center;color: rgb(15, 83, 138);font-weight:600; font-family: 'Nunito', sans-serif; background-color:rgb(201, 205, 211); width: 100%; height: 128px; border-radius: 8px; animation: pulse 1.5s infinite;">
                    <div id="load">
                        <div>G</div>
                        <div>N</div>
                        <div>I</div>
                        <div>D</div>
                        <div>A</div>
                        <div>O</div>
                        <div>L</div>
                    </div>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <div style="background-color: rgb(201, 205, 211); width: 100%; height: 16px; border-radius: 8px; animation: pulse 1.5s infinite;"></div>
                    <div style="background-color: rgb(201, 205, 211); width: 80%; height: 16px; border-radius: 8px; animation: pulse 1.5s infinite;"></div>
                    <div style="background-color: rgb(201, 205, 211); width: 100%; height: 16px; border-radius: 8px; animation: pulse 1.5s infinite;"></div>
                    <div style="background-color: rgb(201, 205, 211); width: 50%; height: 16px; border-radius: 8px; animation: pulse 1.5s infinite;"></div>
                </div>
            </div>
        `;
    
        // Add the loading animation
        document.getElementById('chat-messages').appendChild(loadingDiv);
        document.getElementById('chat-messages').scrollTop = document.getElementById('chat-messages').scrollHeight;
    
        // Add the pulse animation style
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0%, 100% {
                    opacity: 1;
                }
                50% {
                    opacity: 0.5;
                }
            }
        `;
        document.head.appendChild(style);
    
        // Send the message to the server
        fetch('http://127.0.0.1:8000/chat/response/12/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                query: message,
                session_id: sessionId,
                is_new_session: sessionId === null,
                chatbot_id: chatbotId,  // Add this to ensure correct association
                logo_url: ''
            })
        })
        .then(response => response.json())
        .then(data => {
            // Remove loading message
            loadingDiv.remove();
    
            // Append bot response
            appendMessage(data.response, 'bot-message', true);
    
            // Update session ID
            sessionId = data.session_id;
            chatbotId = data.chatbot_id;
        })
        .catch(error => {
            console.error('Error:', error);
            loadingDiv.remove();
            appendMessage("There was an error processing your request. Please try again.", 'bot-message');
        });
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

    // Flow and lead collection functions
// Function to process a step in the flow
function processFlowStep(stepIndex) {
    console.log("Processing step:", stepIndex, "Current flow:", activeFlow);
    
    // Check if we've reached the end of the flow
    if (!activeFlow || !activeFlow.steps || stepIndex >= activeFlow.steps.length) {
        console.log("Flow completed or invalid");
        return;
    }
    
    const step = activeFlow.steps[stepIndex];
    console.log("Processing step data:", step);
    
    // Add bot message
    appendMessage(step.message, 'bot-message');
    
    // If it's a buttons step, add buttons and STOP - wait for user to click a button
    if (step.type === 'buttons' && step.buttons && step.buttons.length > 0) {
        const buttonsHtml = `
            <div class="button-container">
                ${step.buttons.map(button => `
                    <button class="option-button" 
                        data-value="${button.value}"
                        data-step="${stepIndex}"
                    >
                        ${button.label}
                    </button>
                `).join('')}
            </div>
        `;
        appendMessage(buttonsHtml, 'bot-message', true);
        // Do NOT progress automatically for button steps
    } 
    // Only auto-progress for message steps
    else if (step.type === 'message' && stepIndex < activeFlow.steps.length - 1) {
        setTimeout(() => {
            processFlowStep(stepIndex + 1);
        }, 1000);
    }
}


// Function to create a lead form
function createLeadForm(type) {
    console.log("Creating lead form:", type);
    const chatMessages = document.getElementById('chat-messages');
    
    // Remove any existing lead forms to prevent duplicates
    const existingForms = document.querySelectorAll('.lead-form');
    existingForms.forEach(form => form.remove());
    
    const form = document.createElement('div');
    form.classList.add('message', 'bot-message', 'lead-form');

    if (type === 'name') {
        form.innerHTML = `
            <input type="text" class="lead-input" placeholder="Enter your name" required>
            <button class="lead-submit-btn">Submit</button>
        `;
        
        const submitBtn = form.querySelector('.lead-submit-btn');
        const input = form.querySelector('.lead-input');
        
        submitBtn.onclick = () => {
            const name = input.value.trim();
            if (name) {
                leadState.name = name;
                leadState.nameCollected = true;
                form.remove();
                
                // Show confirmation and proceed to phone collection
                appendMessage(`Thank you, ${name}! Could you please provide your phone number?`, 'bot-message');
                setTimeout(() => createLeadForm('phone'), 500);
            } else {
                alert('Please enter your name');
            }
        };
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitBtn.click();
            }
        });
    } else if (type === 'phone') {
        form.innerHTML = `
            <input type="tel" class="lead-input" placeholder="Enter your 10-digit phone number" pattern="[0-9]{10}" required>
            <button class="lead-submit-btn">Submit</button>
        `;
        
        const submitBtn = form.querySelector('.lead-submit-btn');
        const input = form.querySelector('.lead-input');
        
        submitBtn.onclick = () => {
            const phone = input.value.trim();
            if (/^\d{10}$/.test(phone)) {
                leadState.phone = phone;
                leadState.phoneCollected = true;
                form.remove();
                
                // Save the lead data and enable chat
                saveLead();
            } else {
                alert('Please enter a valid 10-digit phone number');
            }
        };
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitBtn.click();
            }
        });
    }

    chatMessages.appendChild(form);
    form.querySelector('.lead-input').focus();
}

function saveLead() {
    if (!leadState.nameCollected || !leadState.phoneCollected) {
        console.error('Lead information incomplete');
        return;
    }

    const leadData = {
        name: leadState.name,
        phone: leadState.phone,
        email: null,
        session_id: sessionId || 'default-session-' + Date.now(),
        // Include these for backward compatibility
        property_selection: userSelections.propertyType?.label || null,
        budget_range: userSelections.budgetRange?.label || null,
        // Add all user selections as a complete object
        user_selections: userSelections,
        chatbot_id: chatbotId || '11'
    };

    console.log('Saving lead with data:', leadData);

    const chatResponseUrl = 'http://127.0.0.1:8000/chat/response/12/';
    const baseUrl = new URL(chatResponseUrl).origin;
    const saveLeadUrl = `${baseUrl}/save-lead/${chatbotId}/`;  // Use variable here

    fetch(saveLeadUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify(leadData),
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Lead saved successfully:', data);
            appendMessage("Thank you for sharing your information! Our team will contact you soon.", 'bot-message');
            
            // Re-enable chat input after lead collection
            updateInputState();
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }
    })
    .catch(error => {
        console.error('Error saving lead:', error);
        appendMessage("There was an error saving your information. Please try again.", 'bot-message');
    });
}

    // Button handling functions
    function initializeButtonHandlers() {
        console.log("Initializing button handlers");
        document.querySelectorAll('.option-button').forEach(button => {
            console.log("Found button:", button);
            button.addEventListener('click', handleButtonClick);
        });
    }

// Handle button clicks
function handleButtonClick(event) {
    event.preventDefault();
    if (isProcessingClick) return;
    isProcessingClick = true;
    
    const button = event.target;
    const value = button.getAttribute('data-value');
    const label = button.textContent.trim();
    const stepIndex = parseInt(button.getAttribute('data-step'), 10);

    console.log("Button clicked:", { value, label, stepIndex });

    // Add user selection as a message
    appendMessage(label, 'user-message');

    // Disable all buttons in the container to prevent multiple selections
    const buttonContainer = button.closest('.button-container');
    if (buttonContainer) {
        const buttons = buttonContainer.querySelectorAll('.option-button');
        buttons.forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
        });
    }

    // Store the user's selection with the question
    if (activeFlow && activeFlow.steps && stepIndex < activeFlow.steps.length) {
        const step = activeFlow.steps[stepIndex];
        const question = step.message;
        
        // Store both question and answer in userSelections
        userSelections[question] = {
            value: value,
            label: label
        };
        
        console.log("Stored selection:", question, label);
        
        // For backward compatibility
        if (question.toLowerCase().includes('property')) {
            userSelections.propertyType = { value, label };
        } else if (question.toLowerCase().includes('budget')) {
            userSelections.budgetRange = { value, label };
        }
    }

    // Update user message count
    userMessageCount++;
    
    // IMPORTANT: Check if we're at the last step OR at the lead collection step
    const isLastStep = (activeFlow && stepIndex >= activeFlow.steps.length - 1);
    const isLeadCollectionStep = (activeFlow && activeFlow.lead_collection_step === stepIndex);
    
    // Only trigger lead collection when appropriate (last step or designated lead step)
    if ((isLastStep || isLeadCollectionStep) && !leadState.nameCollected && leadsEnabled) {
        setTimeout(() => {
            // Clear any existing forms first to prevent duplicates
            document.querySelectorAll('.lead-form').forEach(form => form.remove());
            handleLeadCollection();
            isProcessingClick = false;
        }, 800);
        return;
    }

    // Move to next step if not at the end of flow
    if (activeFlow && activeFlow.steps && stepIndex < activeFlow.steps.length - 1) {
        setTimeout(() => {
            processFlowStep(stepIndex + 1);
            isProcessingClick = false;
        }, 800);
    } else {
        isProcessingClick = false;
    }
}

    // Main initialization function
    function initAll() {
        console.log("Initializing chat widget system");
        
        // Load resources and fetch flows
        Promise.all([...resources.map(loadResource), fetchActiveFlow()])
            .then(() => {
                console.log("Resources loaded, active flow:", activeFlow);
                // Only initialize if not already initialized to prevent duplicates
                if (!widgetInitialized) {
                    initChatWidget();
                }
            })
            .catch(error => {
                console.error('Error initializing chat widget:', error);
                // If not initialized, create just the widget without emergency fallback
                if (!widgetInitialized) {
                    initChatWidget();
                }
            });
    }

    // Initialize when page loads
    window.addEventListener('load', initAll);
})();