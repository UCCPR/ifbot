require('dotenv').config();
const { start } = require('./src/server/index');

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || '0.0.0.0';

const requiredEnv = ['APP_ID', 'APP_SECRET', 'TOKEN', 'ENCODING_AES_KEY'];
const missingEnv = requiredEnv.filter(key => !process.env[key]);

if (missingEnv.length > 0) {
  console.error(`请在 .env 文件中配置以下必填项: ${missingEnv.join(', ')}`);
  process.exit(1);
}

start(PORT, HOST);

process.on('SIGINT', () => {
  console.log('正在关闭服务器...');
  process.exit(0);
});