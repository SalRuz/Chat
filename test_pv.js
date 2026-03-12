console.log('Тестируем prismarine-viewer...');
try {
    const pv = require('prismarine-viewer');
    console.log('✅ Успешно загружен!');
    console.log('Экспорты:', Object.keys(pv));
    console.log('headless тип:', typeof pv.headless);
} catch (err) {
    console.error('❌ Ошибка:', err.message);
    console.error('Путь к модулю:', __dirname);
}
