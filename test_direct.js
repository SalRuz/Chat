// Тест из папки проекта
const path = require('path');
console.log('Текущая папка:', process.cwd());

const pvPath = path.join(__dirname, 'node_modules', 'prismarine-viewer');
console.log('Путь к prismarine-viewer:', pvPath);

try {
    const pv = require(pvPath);
    console.log('✅ Успешно загружен!');
    console.log('Экспорты:', Object.keys(pv));
    console.log('headless:', typeof pv.headless);
    console.log('mineflayer:', typeof pv.mineflayer);
    
    // Проверка headless
    if (pv.headless) {
        console.log('headless функция доступна!');
    }
} catch (err) {
    console.error('❌ Ошибка загрузки:', err.message);
}

// Попробуем загрузить напрямую
try {
    const headless = require(path.join(pvPath, 'lib', 'headless'));
    console.log('✅ headless загружен напрямую!');
} catch (err) {
    console.error('❌ headless напрямую:', err.message);
}
