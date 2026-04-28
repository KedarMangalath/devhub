import re

with open('helpybotest/templates/chat_widget_template.js', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = [
    (r'\.button \{', r'#chat-widget .button {'),
    (r'\.button:hover \{', r'#chat-widget .button:hover {'),
    (r'\.message \{', r'#chat-widget .message {'),
    (r'\.user-message \{', r'#chat-widget .user-message {'),
    (r'\.user-message p \{', r'#chat-widget .user-message p {'),
    (r'\.bot-message \{', r'#chat-widget .bot-message {'),
    (r'\.bot-message:before \{', r'#chat-widget .bot-message:before {'),
    (r'\.bot-message::after \{', r'#chat-widget .bot-message::after {'),
    (r'\.timestamp \{', r'#chat-widget .timestamp {'),
    (r'\.message-actions \{', r'#chat-widget .message-actions {'),
    (r'\.share-button, \.translate-button \{', r'#chat-widget .share-button, #chat-widget .translate-button {'),
    (r'\.share-button:hover, \.translate-button:hover \{', r'#chat-widget .share-button:hover, #chat-widget .translate-button:hover {'),
    (r'\.share-options \{', r'#chat-widget .share-options {'),
    (r'\.share-options button \{', r'#chat-widget .share-options button {'),
    (r'\.share-options button:hover \{', r'#chat-widget .share-options button:hover {'),
    (r'\.page::', r'#chat-widget .page::'),
    (r'\.page \{', r'#chat-widget .page {'),
    (r'\.typing-indicator \{', r'#chat-widget .typing-indicator {'),
    (r'\.typing-indicator span \{', r'#chat-widget .typing-indicator span {'),
    (r'\.options-container \{', r'#chat-widget .options-container {'),
    (r'\.option-btn \{', r'#chat-widget .option-btn {'),
    (r'\.option-btn:hover \{', r'#chat-widget .option-btn:hover {'),
    (r'\.form-container \{', r'#chat-widget .form-container {'),
    (r'\.form-input \{', r'#chat-widget .form-input {'),
    (r'\.form-submit \{', r'#chat-widget .form-submit {'),
    (r'\.form-submit:hover \{', r'#chat-widget .form-submit:hover {'),
    (r'\.product-card \{', r'#chat-widget .product-card {'),
    (r'\.product-image \{', r'#chat-widget .product-image {'),
    (r'\.product-info \{', r'#chat-widget .product-info {'),
    (r'\.product-title \{', r'#chat-widget .product-title {'),
    (r'\.product-price \{', r'#chat-widget .product-price {'),
    (r'\.product-description \{', r'#chat-widget .product-description {'),
    (r'\.product-link \{', r'#chat-widget .product-link {'),
    (r'\.product-link:hover \{', r'#chat-widget .product-link:hover {'),
    (r'\.carousel-container \{', r'#chat-widget .carousel-container {'),
    (r'\.carousel-track \{', r'#chat-widget .carousel-track {'),
    (r'\.carousel-btn \{', r'#chat-widget .carousel-btn {'),
    (r'\.carousel-btn:hover \{', r'#chat-widget .carousel-btn:hover {'),
    (r'\.carousel-btn\.prev \{', r'#chat-widget .carousel-btn.prev {'),
    (r'\.carousel-btn\.next \{', r'#chat-widget .carousel-btn.next {'),
]

for old, new in replacements:
    content = re.sub(old, new, content)

with open('helpybotest/templates/chat_widget_template.js', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done")
