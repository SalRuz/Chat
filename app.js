// Конфигурация Supabase (замените на свои данные)
const SUPABASE_CONFIG = {
    url: 'https://skpykngtzexxcytgqgcv.supabase.co',
    key: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNrcHlrbmd0emV4eGN5dGdxZ2N2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk4OTMyNTYsImV4cCI6MjA2NTQ2OTI1Nn0.9w_pvdUo5eSDrzH47oBYzIsOmJ9kcmshh1vPR79pCts'
};

// Инициализация Supabase
const supabase = supabase.createClient(SUPABASE_CONFIG.url, SUPABASE_CONFIG.key);

// DOM элементы
const elements = {
    messagesContainer: document.getElementById('messages'),
    messageForm: document.getElementById('message-form'),
    messageInput: document.getElementById('message-input'),
    sendButton: document.getElementById('send-button'),
    loadingIndicator: document.getElementById('loading'),
    onlineCount: document.getElementById('online-count')
};

// Генерация случайного имени пользователя и цвета
const user = {
    name: `Аноним-${Math.floor(1000 + Math.random() * 9000)}`,
    color: `hsl(${Math.floor(Math.random() * 360)}, 70%, 60%)`
};

// Состояние приложения
const appState = {
    isSending: false,
    onlineUsers: 0
};

// Функция для добавления сообщения в чат
function addMessageToChat(message, isCurrentUser = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message');
    if (isCurrentUser) messageElement.classList.add('user-message');
    
    const time = new Date(message.created_at).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit'
    });
    
    messageElement.innerHTML = `
        <strong style="color: ${isCurrentUser ? user.color : '#555'}">${message.username}</strong>
        <p>${message.text}</p>
        <span class="message-time">${time}</span>
    `;
    
    elements.messagesContainer.appendChild(messageElement);
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

// Функция для загрузки сообщений
async function loadMessages() {
    try {
        const { data, error } = await supabase
            .from('messages')
            .select('*')
            .order('created_at', { ascending: true })
            .limit(100);
        
        if (error) throw error;
        
        elements.messagesContainer.innerHTML = '';
        if (data.length === 0) {
            elements.messagesContainer.innerHTML = '<div class="text-center text-muted py-3">Нет сообщений</div>';
            return;
        }
        
        data.forEach(message => {
            addMessageToChat(message, message.username === user.name);
        });
    } catch (error) {
        console.error('Ошибка загрузки сообщений:', error);
        elements.messagesContainer.innerHTML = '<div class="text-center text-danger py-3">Ошибка загрузки сообщений</div>';
    } finally {
        elements.loadingIndicator.style.display = 'none';
    }
}

// Функция для отправки сообщения
async function sendMessage() {
    const messageText = elements.messageInput.value.trim();
    if (!messageText || appState.isSending) return;
    
    appState.isSending = true;
    elements.sendButton.disabled = true;
    elements.sendButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    
    try {
        const { error } = await supabase
            .from('messages')
            .insert([{ 
                text: messageText, 
                username: user.name 
            }]);
        
        if (error) throw error;
        
        elements.messageInput.value = '';
    } catch (error) {
        console.error('Ошибка отправки сообщения:', error);
        alert('Не удалось отправить сообщение. Попробуйте снова.');
    } finally {
        appState.isSending = false;
        elements.sendButton.disabled = false;
        elements.sendButton.innerHTML = 'Отправить';
    }
}

// Функция для обновления счетчика онлайн
function updateOnlineCount(count) {
    appState.onlineUsers = count;
    elements.onlineCount.textContent = `${count} онлайн`;
}

// Инициализация приложения
async function initApp() {
    // Загрузка сообщений
    loadMessages();
    
    // Обработчик формы
    elements.messageForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        await sendMessage();
    });
    
    // Подписка на новые сообщения в реальном времени
    supabase
        .channel('public:messages')
        .on(
            'postgres_changes',
            { 
                event: 'INSERT', 
                schema: 'public', 
                table: 'messages' 
            },
            (payload) => {
                addMessageToChat(payload.new, payload.new.username === user.name);
            }
        )
        .subscribe();
    
    // Простая система подсчета онлайн (используем Presence канал)
    const presenceChannel = supabase.channel('online');
    
    presenceChannel
        .on('presence', { event: 'sync' }, () => {
            const state = presenceChannel.presenceState();
            updateOnlineCount(Object.keys(state).length);
        })
        .subscribe(async (status) => {
            if (status === 'SUBSCRIBED') {
                await presenceChannel.track({ 
                    user: user.name,
                    online_at: new Date().toISOString()
                });
            }
        });
}

// Запуск приложения при загрузке страницы
document.addEventListener('DOMContentLoaded', initApp);
