import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { discussionRoutes } from './routes/discussions';
import { initializeDatabase } from './config/database';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 9999;

// 미들웨어
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// 라우트
app.use('/api/discussions', discussionRoutes);

// 테스트 엔드포인트 추가
app.get('/api/test', (req, res) => {
  res.json({ message: '서버가 정상적으로 응답합니다.' });
});

// 서버 시작
const startServer = async () => {
  try {
    // 데이터베이스 초기화
    await initializeDatabase();
    
    // 포트 사용 가능 여부 확인 및 대체 포트 사용
    const tryPort = (port: number): Promise<number> => {
      return new Promise((resolve, reject) => {
        const server = app.listen(port, () => {
          server.close();
          resolve(port);
        });
        
        server.on('error', (err: any) => {
          if (err.code === 'EADDRINUSE') {
            console.log(`포트 ${port}가 이미 사용 중입니다. 다른 포트를 시도합니다.`);
            tryPort(port + 1).then(resolve).catch(reject);
          } else {
            reject(err);
          }
        });
      });
    };
    
    const availablePort = await tryPort(Number(PORT));
    console.log(`사용 가능한 포트를 찾았습니다: ${availablePort}`);
    
    // 서버 시작
    const server = app.listen(availablePort, () => {
      console.log(`서버가 포트 ${availablePort}에서 실행 중입니다.`);
      console.log(`API URL: http://localhost:${availablePort}/api`);
    });
    
    // 종료 시그널 처리
    process.on('SIGTERM', () => {
      console.info('SIGTERM signal received.');
      server.close(() => {
        console.log('Server closed.');
        process.exit(0);
      });
    });
    
  } catch (error) {
    console.error('서버 시작 오류:', error);
    process.exit(1);
  }
};

startServer(); 