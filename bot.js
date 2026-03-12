require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const mineflayer = require('mineflayer');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

// Попытка загрузить prismarine-viewer для скриншотов
let headless = null;
let viewerModule = null;
let viewerEnabled = false;
try {
    // Используем абсолютный путь для обхода проблем с кириллицей
    const pvPath = __dirname + '\\node_modules\\prismarine-viewer';
    const prismarineViewer = require(pvPath);
    headless = prismarineViewer.headless;
    viewerModule = prismarineViewer.viewer;
    viewerEnabled = true;
    console.log('✅ prismarine-viewer загружен (скриншоты доступны)');
} catch (err) {
    console.log('⚠️ prismarine-viewer не найден (скриншоты недоступны)');
    console.log('Ошибка:', err.message);
}

// Путь к папке data (локально или в Docker)
const dataDir = process.env.DATA_DIR || path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
}

// Путь к базе данных
const dbPath = path.join(dataDir, 'bot.db');

// Создаем базу и таблицы при первом запуске
const db = new sqlite3.Database(dbPath, (err) => {
    if (err) {
        console.error('Ошибка открытия базы данных:', err);
        return;
    }
    console.log('✅ База данных подключена:', dbPath);

    // Создаем таблицу сессий
    db.run(`
        CREATE TABLE IF NOT EXISTS sessions (
            chat_id TEXT PRIMARY KEY,
            server_host TEXT,
            server_port INTEGER,
            version TEXT,
            auto_reconnect INTEGER DEFAULT 0,
            chat_enabled INTEGER DEFAULT 0
        )
    `, (err) => {
        if (err) {
            console.error('Ошибка создания таблицы sessions:', err);
        } else {
            console.log('✅ Таблица sessions готова');
        }
    });

    // Таблица активных серверов (для блокировки дубликатов)
    db.run(`
        CREATE TABLE IF NOT EXISTS active_servers (
            server_host TEXT,
            server_port INTEGER,
            owner_chat_id TEXT PRIMARY KEY,
            bot_username TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    `, (err) => {
        if (err) {
            console.error('Ошибка создания таблицы active_servers:', err);
        } else {
            console.log('✅ Таблица active_servers готова');
        }
    });

    // Таблица пользователей, которые используют чат сервера
    db.run(`
        CREATE TABLE IF NOT EXISTS chat_users (
            chat_id TEXT PRIMARY KEY,
            server_host TEXT,
            server_port INTEGER,
            tg_username TEXT,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    `, (err) => {
        if (err) {
            console.error('Ошибка создания таблицы chat_users:', err);
        } else {
            console.log('✅ Таблица chat_users готова');
        }
    });
});

const token = process.env.TELEGRAM_BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });

// Хранилище активных сессий в памяти
const sessions = {};

// Глобальное хранилище подключений к серверам (один сервер = один бот)
const serverConnections = {};

// Загрузка сессии из БД
function loadSessionFromDb(chatId) {
    return new Promise((resolve) => {
        db.get('SELECT * FROM sessions WHERE chat_id = ?', [chatId], (err, row) => {
            if (err || !row) {
                resolve(null);
            } else {
                resolve({
                    server: { host: row.server_host, port: row.server_port },
                    version: row.version,
                    autoReconnect: row.auto_reconnect === 1,
                    chatEnabled: row.chat_enabled === 1
                });
            }
        });
    });
}

// Сохранение сессии в БД
function saveSessionToDb(chatId, session) {
    db.run(
        `INSERT OR REPLACE INTO sessions (chat_id, server_host, server_port, version, auto_reconnect, chat_enabled)
         VALUES (?, ?, ?, ?, ?, ?)`,
        [chatId, session.server?.host || null, session.server?.port || null, session.version || null, 
         session.autoReconnect ? 1 : 0, session.chatEnabled ? 1 : 0],
        (err) => {
            if (err) console.error('Ошибка сохранения сессии:', err);
        }
    );
}

// Удаление сессии из БД
function deleteSessionFromDb(chatId) {
    db.run('DELETE FROM sessions WHERE chat_id = ?', [chatId], (err) => {
        if (err) console.error('Ошибка удаления сессии:', err);
    });
}

// Проверка: занят ли сервер другим пользователем
function isServerOccupied(host, port, excludeChatId = null) {
    const key = `${host}:${port}`;
    if (serverConnections[key] && serverConnections[key].ownerChatId !== excludeChatId) {
        return serverConnections[key].ownerChatId;
    }
    return null;
}

// Регистрация сервера за пользователем (владелец)
function registerServer(host, port, chatId, botUsername) {
    const key = `${host}:${port}`;
    serverConnections[key] = {
        ownerChatId: chatId,
        botUsername: botUsername,
        chatUsers: new Set() // пользователи, которые пишут через этого бота
    };
    
    db.run(
        `INSERT OR REPLACE INTO active_servers (server_host, server_port, owner_chat_id, bot_username)
         VALUES (?, ?, ?, ?)`,
        [host, port, chatId, botUsername],
        (err) => {
            if (err) console.error('Ошибка регистрации сервера:', err);
        }
    );
}

// Освобождение сервера
function unregisterServer(host, port, chatId) {
    const key = `${host}:${port}`;
    if (serverConnections[key] && serverConnections[key].ownerChatId === chatId) {
        delete serverConnections[key];
    }
    
    db.run('DELETE FROM active_servers WHERE server_host = ? AND server_port = ? AND owner_chat_id = ?', 
        [host, port, chatId], (err) => {
            if (err) console.error('Ошибка освобождения сервера:', err);
        }
    );
}

// Добавление пользователя в чат сервера (автоматически при первом сообщении)
function addChatUser(chatId, host, port, tgUsername) {
    const key = `${host}:${port}`;
    if (serverConnections[key]) {
        serverConnections[key].chatUsers.add(chatId);
    }
    
    db.run(
        `INSERT OR REPLACE INTO chat_users (chat_id, server_host, server_port, tg_username)
         VALUES (?, ?, ?, ?)`,
        [chatId, host, port, tgUsername],
        (err) => {
            if (err) console.error('Ошибка добавления пользователя:', err);
        }
    );
}

// Удаление пользователя из чата
function removeChatUser(chatId, host, port) {
    const key = `${host}:${port}`;
    if (serverConnections[key]) {
        serverConnections[key].chatUsers.delete(chatId);
    }
    
    db.run('DELETE FROM chat_users WHERE chat_id = ?', [chatId], (err) => {
        if (err) console.error('Ошибка удаления пользователя:', err);
    });
}

// Получение всех пользователей чата сервера
function getChatUsers(host, port) {
    const key = `${host}:${port}`;
    if (serverConnections[key]) {
        return Array.from(serverConnections[key].chatUsers);
    }
    return [];
}

// Получение владельца сервера
function getServerOwner(host, port) {
    const key = `${host}:${port}`;
    if (serverConnections[key]) {
        return serverConnections[key].ownerChatId;
    }
    return null;
}

// Получение сессии (сначала из памяти, потом из БД)
async function getSession(chatId) {
    if (!sessions[chatId]) {
        const dbSession = await loadSessionFromDb(chatId);
        if (dbSession) {
            sessions[chatId] = {
                server: dbSession.server,
                version: dbSession.version,
                mcBot: null,
                jumpInterval: null,
                autoReconnect: dbSession.autoReconnect || false,
                chatEnabled: dbSession.chatEnabled || false,
                _waiting: null
            };
        } else {
            sessions[chatId] = {
                server: null,
                version: null,
                mcBot: null,
                jumpInterval: null,
                autoReconnect: false,
                chatEnabled: false,
                _waiting: null
            };
        }
    }
    return sessions[chatId];
}

function getMainMenu(session, isOwner = false) {
    const serverText = session.server
        ? `${session.server.host}:${session.server.port}`
        : '❌ Не указан';
    const versionText = session.version || '❌ Не указана';
    const status = session.mcBot ? '🟢 Онлайн' : '🔴 Оффлайн';
    const reconnectText = session.autoReconnect ? '🔔 ВКЛ' : '🔕 ВЫКЛ';
    const chatText = session.chatEnabled ? '🟢 ВКЛ' : '🔴 ВЫКЛ';

    const text =
        `🤖 *Minecraft Bot*\n\n` +
        `📡 Сервер: \`${serverText}\`\n` +
        `🎮 Версия: \`${versionText}\`\n` +
        `📌 Статус: ${status}\n` +
        `🔄 Авто-переподключение: ${reconnectText}\n` +
        `💬 Чат: ${chatText}\n\n` +
        `${isOwner ? '👑 Вы владелец сервера' : '👥 Вы используете чат сервера'}`;

    if (isOwner) {
        // Меню для владельца - полный доступ
        const keyboard = {
            inline_keyboard: [
                [
                    { text: '📡 Сервер', callback_data: 'set_server' },
                    { text: '🎮 Версия', callback_data: 'set_version' },
                ],
                [
                    { text: '▶️ Старт', callback_data: 'start_bot' },
                    { text: '⏹ Стоп', callback_data: 'stop_bot' },
                ],
                [
                    { text: session.autoReconnect ? '🔔 Откл. авто' : '🔕 Вкл. авто', callback_data: 'toggle_reconnect' },
                    { text: session.chatEnabled ? '💬 Откл. чат' : '💬 Вкл. чат', callback_data: 'toggle_chat' },
                ],
            ],
        };
        return { text, keyboard };
    } else {
        // Меню для обычного пользователя - только чат
        const keyboard = {
            inline_keyboard: [
                [
                    { text: session.chatEnabled ? '💬 Откл. чат' : '💬 Вкл. чат', callback_data: 'toggle_chat' },
                ],
            ],
        };
        return { text, keyboard };
    }
}

function cleanupBot(session) {
    if (session.jumpInterval) {
        clearInterval(session.jumpInterval);
        session.jumpInterval = null;
    }
    session.mcBot = null;
}

// Отправка сообщения всем пользователям чата сервера
async function sendToChatUsers(host, port, message, parseMode = null, extraOptions = {}) {
    const chatUsers = getChatUsers(host, port);
    for (const userChatId of chatUsers) {
        try {
            await bot.sendMessage(userChatId, message, {
                parse_mode: parseMode,
                ...extraOptions
            });
        } catch (err) {
            console.error(`Ошибка отправки сообщения в чат ${userChatId}:`, err.message);
        }
    }
}

// Функция создания скриншота через viewer API
async function takeScreenshot(mcBot) {
    const { createCanvas } = require('node-canvas-webgl/lib');
    const { WorldView, Viewer, getBufferFromStream } = viewerModule;
    const THREE = require('three');
    const os = require('os');
    
    const width = 1280;
    const height = 720;
    const viewDistance = 6;
    
    // Копируем текстуры во временную папку для обхода проблем с кириллицей
    const tempDir = os.tmpdir();
    const viewerTempPath = path.join(tempDir, 'prismarine-viewer-textures');
    
    // Копируем только если ещё не скопировано
    if (!fs.existsSync(viewerTempPath)) {
        fs.mkdirSync(viewerTempPath, { recursive: true });
        const texturesDir = path.join(viewerTempPath, 'textures');
        fs.mkdirSync(texturesDir, { recursive: true });
        
        // Копируем все текстуры
        const sourceTextures = path.join(__dirname, 'node_modules', 'prismarine-viewer', 'public', 'textures');
        const textureFiles = fs.readdirSync(sourceTextures);
        for (const file of textureFiles) {
            if (file.endsWith('.png')) {
                fs.copyFileSync(path.join(sourceTextures, file), path.join(texturesDir, file));
            }
        }
    }
    
    // Временно меняем путь к текстурам
    const originalPublicPath = path.join(__dirname, 'node_modules', 'prismarine-viewer', 'public');
    
    const canvas = createCanvas(width, height);
    const renderer = new THREE.WebGLRenderer({ canvas });
    const viewer = new Viewer(renderer);
    
    if (!viewer.setVersion(mcBot.version)) {
        throw new Error('Не удалось установить версию Minecraft');
    }
    
    viewer.setFirstPersonCamera(mcBot.entity.position, mcBot.entity.yaw, mcBot.entity.pitch);
    
    const worldView = new WorldView(mcBot.world, viewDistance, mcBot.entity.position);
    viewer.listen(worldView);
    worldView.init(mcBot.entity.position);
    
    // Ждём загрузки чанков
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    viewer.update();
    renderer.render(viewer.scene, viewer.camera);
    
    const imageStream = canvas.createPNGStream();
    const buffer = await getBufferFromStream(imageStream);
    
    return buffer;
}

// Функция подключения к серверу
async function connectToServer(chatId, session) {
    if (session.mcBot) {
        console.log(`[${chatId}] Бот уже подключен`);
        return;
    }
    if (!session.server || !session.server.host) {
        console.log(`[${chatId}] Сервер не указан`);
        return;
    }
    if (!session.version) {
        console.log(`[${chatId}] Версия не указана`);
        return;
    }

    const { host, port } = session.server;
    
    // Проверяем, занят ли сервер другим пользователем
    const occupiedBy = isServerOccupied(host, port, chatId);
    if (occupiedBy) {
        // Предлагаем использовать чат существующего бота
        bot.sendMessage(chatId, 
            `⚠️ Этот сервер уже занят пользователем (чат ID: \`${occupiedBy}\`).\n\n` +
            `Но вы можете использовать чат этого сервера! Просто напишите любое сообщение ` +
            `и оно будет отправлено в Minecraft от вашего имени.`, 
            { parse_mode: 'Markdown' });
        
        // Автоматически добавляем пользователя в чат
        addChatUser(chatId, host, port, chatId.toString());
        
        // Загружаем сессию владельца и показываем меню
        const ownerSession = await getSession(occupiedBy);
        if (ownerSession && ownerSession.server) {
            const { text, keyboard } = getMainMenu(ownerSession, false);
            bot.sendMessage(chatId, text, { parse_mode: 'Markdown', reply_markup: keyboard });
        }
        return;
    }

    const name = `Bot_${Math.floor(Math.random() * 10000)}`;
    console.log(`[${chatId}] Подключение к ${host}:${port}, версия: ${session.version}`);

    const mcBot = mineflayer.createBot({
        host: host,
        port: port,
        username: name,
        version: session.version === 'auto' ? false : session.version,
        auth: 'offline',
        checkTimeoutInterval: 60000,
        hideErrors: true
    });

    session.mcBot = mcBot;

    // Регистрируем сервер за этим пользователем (владелец)
    registerServer(host, port, chatId, name);
    // Добавляем владельца в чат
    addChatUser(chatId, host, port, chatId.toString());

    // Таймер таймаута спавна
    const spawnTimeout = setTimeout(async () => {
        if (session.mcBot && !session.mcBot.entity) {
            console.log(`[${chatId}] Тайм-аут ожидания спавна`);
            cleanupBot(session);
            unregisterServer(host, port, chatId);
            try {
                await sendToChatUsers(host, port, '❌ Подключиться не удалось, так как серв отключен.');
            } catch (e) {}
            try { mcBot.quit(); } catch {}
            // Если включено авто-переподключение, пробуем снова
            if (session.autoReconnect) {
                try {
                    await sendToChatUsers(host, port, '🔄 Мгновенная попытка переподключения с новым ником...');
                } catch (e) {}
                setTimeout(() => connectToServer(chatId, session), 1000);
            }
        }
    }, 40000);

    mcBot.on('login', () => {
        console.log(`[${chatId}] Бот вошел в сеть как ${name}`);
    });

    mcBot.once('spawn', async () => {
        clearTimeout(spawnTimeout);
        console.log(`[${chatId}] Бот заспавнился на сервере`);

        session.jumpInterval = setInterval(() => {
            try {
                mcBot.setControlState('jump', true);
                setTimeout(() => mcBot.setControlState('jump', false), 300);
            } catch {}
        }, 1500);

        await sendToChatUsers(host, port, '✅ Бот подключён и прыгает!');

        const { text, keyboard } = getMainMenu(session, true);
        await sendToChatUsers(host, port, text, 'Markdown', { reply_markup: keyboard });
    });

    // Обработка сообщений из чата Minecraft
    mcBot.on('chat', async (username, message) => {
        // Пропускаем сообщения от самого бота
        if (username === name) return;

        const formattedMessage = `🎮 <b>${username}</b>: ${message}`;
        
        // Отправляем всем пользователям чата
        await sendToChatUsers(host, port, formattedMessage, 'HTML');
    });

    // Уведомления о присоединении игроков
    mcBot.on('playerJoined', async (player) => {
        const joinMessage = `<b>➕ ${player.username} присоединился к игре</b>`;
        await sendToChatUsers(host, port, joinMessage, 'HTML');
    });

    // Уведомления о выходе игроков
    mcBot.on('playerLeft', async (player) => {
        const leaveMessage = `<b>➖ ${player.username} покинул игру</b>`;
        await sendToChatUsers(host, port, leaveMessage, 'HTML');
    });

    // Уведомления о смерти (через сообщение в чат)
    mcBot.on('death', async () => {
        const deathMessage = '<b>💀 Бот умер!</b>';
        await sendToChatUsers(host, port, deathMessage, 'HTML');
    });

    // Обработка сообщений о смерти в чате (если сервер отправляет такие)
    mcBot.on('messagestr', async (message, jsonMsg, type) => {
        // Проверяем на сообщения о смерти игроков
        if (type === 'chat' || type === 'system') {
            const deathPatterns = [
                /(.+) died$/,
                /(.+) was slain by (.+)/,
                /(.+) was killed by (.+)/,
                /(.+) went up in flames$/,
                /(.+) fell off a place$/,
                /(.+) fell from a high place$/,
                /(.+) hit the ground too hard$/,
                /(.+) drowned$/,
                /(.+) suffocated$/,
                /(.+) starved$/,
                /(.+) tried to swim in lava$/,
                /(.+) was shot by (.+)/,
                /(.+) was blown up by (.+)/,
            ];
            
            for (const pattern of deathPatterns) {
                const match = message.match(pattern);
                if (match) {
                    const deathMessage = `<b>💀 ${match[1]} умер${match[2] ? ` от ${match[2]}` : ''}</b>`;
                    await sendToChatUsers(host, port, deathMessage, 'HTML');
                    break;
                }
            }
        }
    });

    mcBot.on('kicked', async (reason) => {
        clearTimeout(spawnTimeout);
        console.log(`[${chatId}] Бот кикнут: ${reason}`);
        cleanupBot(session);
        unregisterServer(host, port, chatId);
        await sendToChatUsers(host, port, '🚫 <b>Бот кикнут с сервера</b>.', 'HTML');
        
        // Мгновенное переподключение с новым ником (даже если забанен)
        if (session.autoReconnect) {
            await sendToChatUsers(host, port, '🔄 Мгновенная попытка переподключения с новым ником...');
            setTimeout(() => connectToServer(chatId, session), 1000);
        }
    });

    mcBot.on('error', async (err) => {
        clearTimeout(spawnTimeout);
        console.error(`[${chatId}] Ошибка Mineflayer:`, err);
        cleanupBot(session);
        unregisterServer(host, port, chatId);

        // Проверяем, является ли ошибкой недоступность сервера
        const serverOffline = err.message?.includes('ECONNREFUSED') ||
                              err.message?.includes('ENOTFOUND') ||
                              err.message?.includes('ETIMEDOUT') ||
                              err.message?.includes('connect ECONNREFUSED');

        if (serverOffline) {
            await sendToChatUsers(host, port, '❌ Подключиться не удалось, так как серв отключен.');
        } else {
            await sendToChatUsers(host, port, `❌ Ошибка: \`${err.message}\``, 'Markdown');
        }

        // Мгновенное переподключение при ошибке (если не сервер отключен)
        if (session.autoReconnect && !serverOffline) {
            await sendToChatUsers(host, port, '🔄 Мгновенная попытка переподключения с новым ником...');
            setTimeout(() => connectToServer(chatId, session), 1000);
        }
    });

    mcBot.on('end', async (reason) => {
        clearTimeout(spawnTimeout);
        console.log(`[${chatId}] Соединение разорвано: ${reason}`);
        if (session.mcBot) {
            cleanupBot(session);
            unregisterServer(host, port, chatId);

            // Проверяем причину отключения
            const serverOffline = reason?.includes('Connection closed') ||
                                  reason?.includes('ECONNREFUSED') ||
                                  reason?.includes('ENOTFOUND');

            if (serverOffline) {
                await sendToChatUsers(host, port, '❌ Подключиться не удалось, так как серв отключен.');
            } else {
                await sendToChatUsers(host, port, '🔌 Бот отключён.');
            }

            // Мгновенное переподключение (если не сервер отключен)
            if (session.autoReconnect && !serverOffline) {
                await sendToChatUsers(host, port, '🔄 Мгновенная попытка переподключения с новым ником...');
                setTimeout(() => connectToServer(chatId, session), 1000);
            }
        }
    });
}

// /start
bot.onText(/\/start/, async (msg) => {
    const session = await getSession(msg.chat.id);
    
    // Проверяем, является ли пользователь владельцем сервера
    let isOwner = false;
    if (session.server) {
        const ownerChatId = getServerOwner(session.server.host, session.server.port);
        isOwner = ownerChatId === msg.chat.id.toString();
    }
    
    const { text, keyboard } = getMainMenu(session, isOwner);
    bot.sendMessage(msg.chat.id, text, {
        parse_mode: 'Markdown',
        reply_markup: keyboard,
    });
});

// /chat - быстрая команда для включения/выключения чата
bot.onText(/\/chat/, async (msg) => {
    const chatId = msg.chat.id;
    const session = await getSession(chatId);
    
    // Проверяем владельца ли
    let isOwner = false;
    if (session.server) {
        const ownerChatId = getServerOwner(session.server.host, session.server.port);
        isOwner = ownerChatId === chatId.toString();
    }
    
    if (!isOwner && (!session.server || !session.mcBot)) {
        // Проверяем, есть ли активный сервер с этим пользователем в чате
        for (const [key, conn] of Object.entries(serverConnections)) {
            if (conn.chatUsers.has(chatId.toString())) {
                const [host, port] = key.split(':');
                session.server = { host, port: parseInt(port) };
                session.mcBot = serverConnections[key].mcBot;
                break;
            }
        }
    }
    
    if (!session.server) {
        return bot.sendMessage(chatId, '❌ Сначала подключитесь к серверу.');
    }
    
    session.chatEnabled = !session.chatEnabled;
    saveSessionToDb(chatId, session);
    
    const status = session.chatEnabled ? '✅ включен' : '❌ выключен';
    bot.sendMessage(chatId, `Чат ${status}`);
});

// /screen - сделать скриншот
bot.onText(/\/скрин|\/screen|\/screenshot/i, async (msg) => {
    const chatId = msg.chat.id;
    const session = await getSession(chatId);
    
    // Проверяем, есть ли у пользователя доступ к серверу
    let hasAccess = false;
    let targetSession = session;
    
    if (session.server) {
        const ownerChatId = getServerOwner(session.server.host, session.server.port);
        hasAccess = ownerChatId === chatId.toString() || session.chatEnabled;
    }
    
    // Если нет доступа, проверяем другие активные сервера
    if (!hasAccess) {
        for (const [key, conn] of Object.entries(serverConnections)) {
            if (conn.chatUsers.has(chatId.toString())) {
                const [host, port] = key.split(':');
                const ownerSession = await getSession(conn.ownerChatId);
                if (ownerSession && ownerSession.mcBot) {
                    targetSession = ownerSession;
                    hasAccess = true;
                    break;
                }
            }
        }
    }
    
    if (!hasAccess || !targetSession.mcBot) {
        return bot.sendMessage(chatId, '❌ Бот не подключён к серверу.');
    }

    // Проверяем доступность скриншотов
    if (!viewerEnabled || !viewerModule) {
        return bot.sendMessage(chatId, '📸 Скриншоты недоступны.\n\nУстановите пакет для скриншотов:\n`npm install prismarine-viewer node-canvas-webgl`\n\nПосле установки перезапустите бота.');
    }

    bot.sendMessage(chatId, '📸 Делаю скриншот...');

    try {
        // Делаем скриншот через viewer API
        const screenshotBuffer = await takeScreenshot(targetSession.mcBot);

        // Отправляем буфер
        await bot.sendPhoto(chatId, screenshotBuffer, { caption: '📸 Скриншот с сервера' });
    } catch (err) {
        console.error('Ошибка скриншота:', err);
        bot.sendMessage(chatId, '❌ Не удалось сделать скриншот.\n\nВозможно:\n• Бот ещё не загрузил чанки (подождите 5-10 сек)\n• Нет видеокарты или драйверов\n• Недостаточно памяти');
    }
});

// Кнопки
bot.on('callback_query', async (query) => {
    const chatId = query.message.chat.id;
    const session = await getSession(chatId);
    
    // Проверяем, является ли пользователь владельцем
    let isOwner = false;
    if (session.server) {
        const ownerChatId = getServerOwner(session.server.host, session.server.port);
        isOwner = ownerChatId === chatId.toString();
    }

    console.log(`[${chatId}] Callback: ${query.data}, владелец: ${isOwner}`);

    // Блокируем действия не-владельцев кроме включения/выключения чата
    if (!isOwner && query.data !== 'toggle_chat') {
        await bot.answerCallbackQuery(query.id, {
            text: '⚠️ Только владелец сервера может управлять ботом.',
            show_alert: true
        });
        return;
    }

    if (query.data === 'set_server') {
        session._waiting = 'server';
        await bot.answerCallbackQuery(query.id);
        await bot.sendMessage(chatId, '📡 Введите адрес сервера:\n`host:port` или просто `host`', {
            parse_mode: 'Markdown',
        });
        return;
    }

    if (query.data === 'set_version') {
        await bot.answerCallbackQuery(query.id);
        await bot.sendMessage(chatId, '🎮 Выберите версию:', {
            reply_markup: {
                inline_keyboard: [
                    [
                        { text: '1.8.9', callback_data: 'ver_1.8.9' },
                        { text: '1.12.2', callback_data: 'ver_1.12.2' },
                        { text: '1.16.5', callback_data: 'ver_1.16.5' },
                    ],
                    [
                        { text: '1.17.1', callback_data: 'ver_1.17.1' },
                        { text: '1.18.2', callback_data: 'ver_1.18.2' },
                        { text: '1.19.4', callback_data: 'ver_1.19.4' },
                    ],
                    [
                        { text: '1.20.1', callback_data: 'ver_1.20.1' },
                        { text: '1.20.4', callback_data: 'ver_1.20.4' },
                        { text: '1.21', callback_data: 'ver_1.21' },
                    ],
                    [
                        { text: '🔄 Авто', callback_data: 'ver_auto' },
                        { text: '✏️ Ввести вручную', callback_data: 'ver_custom' }
                    ],
                ],
            },
        });
        return;
    }

    if (query.data.startsWith('ver_')) {
        const ver = query.data.replace('ver_', '');
        if (ver === 'custom') {
            session._waiting = 'version';
            await bot.answerCallbackQuery(query.id);
            await bot.sendMessage(chatId, '✏️ Введите версию (например `1.19.2`):', {
                parse_mode: 'Markdown',
            });
            return;
        }
        session.version = ver;
        session._waiting = null;
        await bot.answerCallbackQuery(query.id);
        saveSessionToDb(chatId, session);
        const { text, keyboard } = getMainMenu(session, true);
        await bot.sendMessage(chatId, text, { parse_mode: 'Markdown', reply_markup: keyboard });
        return;
    }

    if (query.data === 'toggle_reconnect') {
        session.autoReconnect = !session.autoReconnect;
        saveSessionToDb(chatId, session);
        await bot.answerCallbackQuery(query.id, {
            text: session.autoReconnect ? '✅ Авто-переподключение включено' : '❌ Авто-переподключение выключено'
        });
        const { text, keyboard } = getMainMenu(session, true);
        await bot.editMessageText(text, {
            chat_id: chatId,
            message_id: query.message.message_id,
            parse_mode: 'Markdown',
            reply_markup: keyboard
        });
        return;
    }

    if (query.data === 'toggle_chat') {
        session.chatEnabled = !session.chatEnabled;
        saveSessionToDb(chatId, session);
        
        const status = session.chatEnabled ? '✅ включен' : '❌ выключен';
        await bot.answerCallbackQuery(query.id, {
            text: `Чат ${status}`
        });
        
        const { text, keyboard } = getMainMenu(session, isOwner);
        await bot.editMessageText(text, {
            chat_id: chatId,
            message_id: query.message.message_id,
            parse_mode: 'Markdown',
            reply_markup: keyboard
        });
        return;
    }

    if (query.data === 'start_bot') {
        await bot.answerCallbackQuery(query.id);

        if (session.mcBot) return bot.sendMessage(chatId, '⚠️ Бот уже запущен.');
        if (!session.server || !session.server.host) {
            return bot.sendMessage(chatId, '❌ Укажите сервер (нажмите 📡 Сервер).');
        }
        if (!session.version) return bot.sendMessage(chatId, '❌ Укажите версию.');

        saveSessionToDb(chatId, session);
        await connectToServer(chatId, session);
        return;
    }

    if (query.data === 'stop_bot') {
        await bot.answerCallbackQuery(query.id);
        if (!session.mcBot) return bot.sendMessage(chatId, '⚠️ Бот не запущен.');
        
        const { host, port } = session.server;
        try { session.mcBot.quit(); } catch {}
        cleanupBot(session);
        unregisterServer(host, port, chatId);
        
        const { text, keyboard } = getMainMenu(session, true);
        await bot.sendMessage(chatId, '✅ Бот остановлен.');
        await bot.sendMessage(chatId, text, { parse_mode: 'Markdown', reply_markup: keyboard });
        return;
    }
});

// Текстовый ввод
bot.on('message', async (msg) => {
    if (!msg.text || msg.text.startsWith('/')) return;
    const chatId = msg.chat.id;
    const session = await getSession(chatId);

    console.log(`[${chatId}] Получено сообщение: ${msg.text}, _waiting=${session._waiting}`);

    if (session._waiting === 'server') {
        let rawInput = msg.text.trim().replace(/^https?:\/\//, '');
        const parts = rawInput.split(':');
        const host = parts[0];
        const port = parts[1] ? parseInt(parts[1]) : 25565;
        if (!host || isNaN(port)) {
            return bot.sendMessage(chatId, '❌ Неверный формат.');
        }
        session.server = { host, port };
        session._waiting = null;
        saveSessionToDb(chatId, session);
        console.log(`[${chatId}] Сервер сохранён: ${JSON.stringify(session.server)}`);
        
        // Проверяем, занят ли сервер
        const ownerChatId = getServerOwner(host, port);
        const isOwner = ownerChatId === chatId.toString();
        
        const { text, keyboard } = getMainMenu(session, isOwner);
        bot.sendMessage(chatId, text, { parse_mode: 'Markdown', reply_markup: keyboard });
        return;
    }

    if (session._waiting === 'version') {
        const ver = msg.text.trim();
        if (!/^\d+\.\d+(\.\d+)?$/.test(ver)) {
            return bot.sendMessage(chatId, '❌ Неверный формат. Пример: `1.20.4`', { parse_mode: 'Markdown' });
        }
        session.version = ver;
        session._waiting = null;
        saveSessionToDb(chatId, session);
        const { text, keyboard } = getMainMenu(session, true);
        bot.sendMessage(chatId, text, { parse_mode: 'Markdown', reply_markup: keyboard });
        return;
    }

    // Если чат включен - отправляем сообщение в Minecraft от имени пользователя
    if (session.chatEnabled && session.server) {
        // Проверяем, есть ли доступ к серверу (владелец или пользователь чата)
        let hasAccess = false;
        let targetSession = session;
        
        const ownerChatId = getServerOwner(session.server.host, session.server.port);
        if (ownerChatId === chatId.toString()) {
            hasAccess = true;
        } else if (session.mcBot) {
            hasAccess = true;
        } else {
            // Ищем активный сервер с этим пользователем
            for (const [key, conn] of Object.entries(serverConnections)) {
                if (conn.chatUsers.has(chatId.toString())) {
                    const [host, port] = key.split(':');
                    const ownerSession = await getSession(conn.ownerChatId);
                    if (ownerSession && ownerSession.mcBot) {
                        targetSession = ownerSession;
                        hasAccess = true;
                        break;
                    }
                }
            }
        }
        
        if (hasAccess && targetSession.mcBot) {
            const tgUser = msg.from.username || msg.from.first_name || 'Пользователь';
            const minecraftMessage = `[${tgUser}] ${msg.text}`;
            
            targetSession.mcBot.chat(minecraftMessage);
            console.log(`[${chatId}] Отправлено в Minecraft: ${minecraftMessage}`);
            
            // Добавляем пользователя в чат если ещё не добавлен
            addChatUser(chatId, targetSession.server.host, targetSession.server.port, tgUser);
        } else {
            bot.sendMessage(chatId, '❌ Бот не подключён к серверу.');
        }
        return;
    }
});

// Восстановление сессий при перезапуске бота
async function restoreSessions() {
    return new Promise((resolve) => {
        db.all('SELECT * FROM sessions WHERE auto_reconnect = 1', [], async (err, rows) => {
            if (err) {
                console.error('Ошибка восстановления сессий:', err);
                resolve();
                return;
            }
            if (rows.length === 0) {
                console.log('Нет сессий для восстановления');
                resolve();
                return;
            }
            console.log(`🔄 Восстанавливаю ${rows.length} сессий...`);
            for (const row of rows) {
                const chatId = row.chat_id;
                sessions[chatId] = {
                    server: { host: row.server_host, port: row.server_port },
                    version: row.version,
                    mcBot: null,
                    jumpInterval: null,
                    autoReconnect: true,
                    chatEnabled: row.chat_enabled === 1,
                    _waiting: null
                };
                console.log(`[${chatId}] Восстановлена сессия: ${row.server_host}:${row.server_port}`);
                // Ждем 2 секунды между подключениями
                await new Promise(r => setTimeout(r, 2000));
                await connectToServer(chatId, sessions[chatId]);
            }
            resolve();
        });
    });
}

// Запуск
console.log('🚀 Бот запущен...');
restoreSessions().then(() => {
    console.log('✅ Восстановление завершено');
});
