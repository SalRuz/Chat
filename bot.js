// bot.js
require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const mineflayer = require('mineflayer');
const mc = require('minecraft-protocol');
const sqlite3 = require('sqlite3').verbose();

const TOKEN = process.env.TELEGRAM_BOT_TOKEN;
if (!TOKEN) {
    console.error('❌ TELEGRAM_BOT_TOKEN не установлен в .env');
    process.exit(1);
}

const bot = new TelegramBot(TOKEN, { polling: true });
const db = new sqlite3.Database('/app/data/bot.db');

const activeBots = new Map();

// Функция для безопасного добавления колонки
function addColumnIfNotExists(tableName, columnName, columnType, defaultValue = null) {
    return new Promise((resolve) => {
        db.all(`PRAGMA table_info(${tableName})`, (err, columns) => {
            if (err) {
                console.error(`Ошибка проверки колонок ${tableName}:`, err);
                resolve();
                return;
            }
            
            const columnExists = columns.some(col => col.name === columnName);
            
            if (!columnExists) {
                const defaultVal = defaultValue !== null ? ` DEFAULT ${defaultValue}` : '';
                const sql = `ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnType}${defaultVal}`;
                db.run(sql, (err) => {
                    if (err) {
                        console.error(`Ошибка добавления колонки ${columnName}:`, err);
                    } else {
                        console.log(`✅ Добавлена колонка ${tableName}.${columnName}`);
                    }
                    resolve();
                });
            } else {
                resolve();
            }
        });
    });
}

// Инициализация базы данных с миграцией
async function initDatabase() {    return new Promise((resolve, reject) => {
        db.run(`CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_owner INTEGER DEFAULT 0,
            server_host TEXT,
            server_port INTEGER,
            server_version TEXT,
            bot_nickname TEXT,
            is_active INTEGER DEFAULT 0
        )`, (err) => {
            if (err) return reject(err);
            
            db.run(`CREATE TABLE IF NOT EXISTS chat_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                is_allowed INTEGER DEFAULT 1
            )`, (err) => {
                if (err) return reject(err);
                
                db.run(`CREATE TABLE IF NOT EXISTS active_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host TEXT,
                    port INTEGER,
                    version TEXT,
                    nickname TEXT,
                    owner_id INTEGER
                )`, async (err) => {
                    if (err) return reject(err);
                    
                    try {
                        await addColumnIfNotExists('sessions', 'is_active', 'INTEGER', 0);
                        await addColumnIfNotExists('sessions', 'server_version', 'TEXT');
                        await addColumnIfNotExists('sessions', 'bot_nickname', 'TEXT');
                        await addColumnIfNotExists('sessions', 'server_host', 'TEXT');
                        await addColumnIfNotExists('sessions', 'server_port', 'INTEGER');
                        await addColumnIfNotExists('sessions', 'is_owner', 'INTEGER', 0);
                        
                        console.log('✅ База данных готова');
                        resolve();
                    } catch (err) {
                        console.error('Ошибка миграции БД:', err);
                        reject(err);
                    }
                });
            });
        });
    });
}
// Функция автоматического определения версии сервера
async function detectServerVersion(host, port) {
    return new Promise((resolve, reject) => {
        console.log(`🔍 Определяю версию сервера ${host}:${port}...`);
        
        mc.ping({
            host: host,
            port: port,
            closeTimeout: 5000,
            noPongTimeout: 5000
        }, (err, response) => {
            if (err) {
                console.error('❌ Ошибка ping:', err.message);
                reject(new Error(`Не удалось подключиться к серверу: ${err.message}`));
                return;
            }
            
            if (response && response.version) {
                const version = response.version.name;
                console.log(`✅ Обнаружена версия: ${version}`);
                resolve(version);
            } else {
                reject(new Error('Сервер не вернул информацию о версии'));
            }
        });
    });
}

// Функция подключения к серверу
async function connectToServer(userId, host, port, nickname) {
    try {
        const version = await detectServerVersion(host, port);
        
        console.log(`[${userId}] Подключение к ${host}:${port}, версия: ${version}, ник: ${nickname}`);
        
        const mcBot = mineflayer.createBot({
            host: host,
            port: port,
            version: version,
            username: nickname,
            auth: 'offline'
        });
        
        const jumpInterval = setInterval(() => {
            if (mcBot.entity && mcBot.physicsEnabled) {
                mcBot.setControlState('jump', true);
                setTimeout(() => mcBot.setControlState('jump', false), 500);
            }
        }, 1500);
                mcBot.on('spawn', () => {
            console.log(`[${userId}] ✅ Бот заспавнился на сервере!`);
            sendToTelegram(userId, `✅ Бот успешно зашел на сервер ${host}:${port}\n Версия: ${version}\n👤 Ник: ${nickname}`);
            db.run('UPDATE sessions SET server_version = ? WHERE user_id = ?', [version, userId]);
        });
        
        mcBot.on('chat', (username, message) => {
            if (username !== nickname) {
                sendToTelegram(userId, `💬 <b>${username}:</b> ${escapeHtml(message)}`, 'HTML');
            }
        });
        
        mcBot.on('playerJoined', (player) => {
            if (player.username !== nickname) {
                sendToTelegram(userId, `➕ <b>${player.username}</b> зашел на сервер`, 'HTML');
            }
        });
        
        mcBot.on('playerLeft', (player) => {
            if (player.username !== nickname) {
                sendToTelegram(userId, `➖ <b>${player.username}</b> вышел с сервера`, 'HTML');
            }
        });
        
        mcBot.on('death', () => {
            sendToTelegram(userId, `💀 Бот умер!`);
        });
        
        mcBot.on('kicked', (reason) => {
            console.log(`[${userId}] Кикнут:`, reason);
            sendToTelegram(userId, `🚫 Бот кикнут с сервера: ${reason}`);
            cleanupBot(userId);
        });
        
        mcBot.on('error', (err) => {
            console.error(`[${userId}] Ошибка:`, err.message);
            sendToTelegram(userId, ` Ошибка подключения: ${err.message}`);
        });
        
        mcBot.on('end', () => {
            console.log(`[${userId}] Отключен от сервера`);
            sendToTelegram(userId, `🔌 Бот отключен от сервера`);
            cleanupBot(userId);
        });
        
        activeBots.set(userId, { bot: mcBot, jumpInterval });
        db.run('UPDATE sessions SET is_active = 1 WHERE user_id = ?', [userId]);
        
    } catch (err) {
        console.error(`[${userId}] Ошибка подключения:`, err.message);        sendToTelegram(userId, ` Не удалось подключиться: ${err.message}`);
    }
}

function cleanupBot(userId) {
    const data = activeBots.get(userId);
    if (data) {
        clearInterval(data.jumpInterval);
        try {
            data.bot.quit();
        } catch (e) {}
        activeBots.delete(userId);
    }
    db.run('UPDATE sessions SET is_active = 0 WHERE user_id = ?', [userId]);
}

function sendToTelegram(userId, text, parseMode = null) {
    bot.sendMessage(userId, text, { parse_mode: parseMode }).catch(err => {
        console.error(`Ошибка отправки в Telegram:`, err.message);
        if (err.message.includes('parse entities') || err.message.includes('Bad Request')) {
            bot.sendMessage(userId, text).catch(e => {
                console.error(`Повторная ошибка отправки:`, e.message);
            });
        }
    });
}

function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const username = msg.from.username || msg.from.first_name;
    
    db.get('SELECT * FROM sessions WHERE user_id = ?', [chatId], (err, row) => {
        if (err) {
            console.error(err);
            return;
        }
        
        if (!row) {
            const isFirstUser = activeBots.size === 0;
            db.run(
                'INSERT INTO sessions (user_id, username, is_owner) VALUES (?, ?, ?)',
                [chatId, username, isFirstUser ? 1 : 0]
            );            
            bot.sendMessage(chatId, 
                `👋 Привет, ${username}!\n\n` +
                `Я бот для управления Minecraft через Telegram.\n\n` +
                ` <b>Команды:</b>\n` +
                `/connect {host} {port} - подключиться к серверу\n` +
                `/disconnect - отключиться\n` +
                `/status - статус бота\n` +
                `/nick {ник} - установить ник\n\n` +
                `Просто пиши сообщения, чтобы общаться в Minecraft чате!`,
                { parse_mode: 'HTML' }
            );
        } else {
            bot.sendMessage(chatId, `С возвращением, ${username}!\nИспользуй /status чтобы проверить статус.`);
        }
    });
});

bot.onText(/\/connect (.+)/, (msg, match) => {
    const chatId = msg.chat.id;
    const input = match[1].trim();
    
    let host, port;
    
    // Проверяем, есть ли порт в адресе (разделен двоеточием)
    if (input.includes(':')) {
        const parts = input.split(':');
        host = parts[0];
        port = parseInt(parts[1]);
    } else {
        // Если порта нет, используем дефолтный
        const args = input.split(' ');
        host = args[0];
        port = args[1] ? parseInt(args[1]) : 25565;
    }
    
    if (!host) {
        bot.sendMessage(chatId, ' Использование: /connect {host} [port]\nПример: /connect example.com:25565');
        return;
    }
    
    if (isNaN(port) || port < 1 || port > 65535) {
        bot.sendMessage(chatId, '❌ Неверный порт. Используйте число от 1 до 65535');
        return;
    }
    
    // Получаем ник пользователя
    db.get('SELECT bot_nickname FROM sessions WHERE user_id = ?', [chatId], (err, row) => {
        const nickname = (row && row.bot_nickname) || `User_bot_${Math.floor(Math.random() * 10000)}`;
                // Сохраняем сервер
        db.run(
            'UPDATE sessions SET server_host = ?, server_port = ?, bot_nickname = ? WHERE user_id = ?',
            [host, port, nickname, chatId]
        );
        
        // Сохраняем в active_servers
        db.get('SELECT * FROM active_servers WHERE owner_id = ?', [chatId], (err, activeRow) => {
            if (activeRow) {
                db.run(
                    'UPDATE active_servers SET host = ?, port = ?, nickname = ? WHERE owner_id = ?',
                    [host, port, nickname, chatId]
                );
            } else {
                db.run(
                    'INSERT INTO active_servers (host, port, nickname, owner_id) VALUES (?, ?, ?, ?)',
                    [host, port, nickname, chatId]
                );
            }
        });
        
        bot.sendMessage(chatId, `🔄 Подключаюсь к ${host}:${port}...\n🔍 Автоматически определяю версию...`);
        connectToServer(chatId, host, port, nickname);
    });
});

bot.onText(/\/disconnect/, (msg) => {
    const chatId = msg.chat.id;
    if (activeBots.has(chatId)) {
        cleanupBot(chatId);
        bot.sendMessage(chatId, '✅ Бот отключен от сервера');
    } else {
        bot.sendMessage(chatId, '❌ Бот не подключен к серверу');
    }
});

bot.onText(/\/status/, (msg) => {
    const chatId = msg.chat.id;
    db.get('SELECT * FROM sessions WHERE user_id = ?', [chatId], (err, row) => {
        if (!row) {
            bot.sendMessage(chatId, '❌ Вы не зарегистрированы. Используйте /start');
            return;
        }
        
        const isActive = activeBots.has(chatId);
        let status = `📊 <b>Статус бота:</b>\n\n`;
        status += `👤 Ник: ${row.bot_nickname || 'не установлен'}\n`;
        status += `🖥 Сервер: ${row.server_host || 'не подключен'}:${row.server_port || ''}\n`;
        status += `📦 Версия: ${row.server_version || 'не определена'}\n`;
        status += `🔌 Статус: ${isActive ? ' Онлайн' : '🔴 Оффлайн'}`;        
        bot.sendMessage(chatId, status, { parse_mode: 'HTML' });
    });
});

bot.onText(/\/nick (.+)/, (msg, match) => {
    const chatId = msg.chat.id;
    const nickname = match[1].trim();
    
    if (nickname.length < 3 || nickname.length > 16) {
        bot.sendMessage(chatId, '❌ Ник должен быть от 3 до 16 символов');
        return;
    }
    
    db.run('UPDATE sessions SET bot_nickname = ? WHERE user_id = ?', [nickname, chatId]);
    bot.sendMessage(chatId, `✅ Ник изменен на: ${nickname}`);
});

bot.on('message', (msg) => {
    if (!msg.text || msg.text.startsWith('/')) return;
    
    const chatId = msg.chat.id;
    if (!activeBots.has(chatId)) return;
    
    const data = activeBots.get(chatId);
    const mcBot = data.bot;
    
    if (mcBot && mcBot.entity) {
        mcBot.chat(msg.text);
    }
});

async function startBot() {
    console.log('🚀 Запуск бота...');
    try {
        await initDatabase();
        
        console.log('🔄 Восстанавливаю сессии...');
        db.all('SELECT * FROM sessions WHERE is_active = 1 AND server_host IS NOT NULL', [], (err, rows) => {
            if (err) {
                console.error('Ошибка восстановления:', err);
                return;
            }
            
            console.log(`🔄 Найдено ${rows.length} активных сессий`);
            rows.forEach(row => {
                console.log(`[${row.user_id}] Восстановлена: ${row.server_host}:${row.server_port}`);
                connectToServer(row.user_id, row.server_host, row.server_port, row.bot_nickname);
            });
        });        
        console.log('✅ Бот запущен!');
    } catch (err) {
        console.error(' Критическая ошибка запуска:', err);
        process.exit(1);
    }
}

startBot();
