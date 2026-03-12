try {
    const pv = require('./node_modules/prismarine-viewer');
    console.log('=== prismarine-viewer загружен ===');
    console.log('Экспорты:', Object.keys(pv));
    console.log('headless:', typeof pv.headless);
    console.log('mineflayer:', typeof pv.mineflayer);
} catch (err) {
    console.error('Ошибка:', err.message);
}
