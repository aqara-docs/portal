import mysql from 'mysql2/promise';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../../../.env') });

interface CustomPoolOptions extends mysql.PoolOptions {
  charset?: string;
  supportBigNumbers?: boolean;
  dateStrings?: boolean;
  decimalNumbers?: boolean;
  socketPath?: string;
}

const poolConfig: CustomPoolOptions = {
  socketPath: '/tmp/mysql.sock',
  user: process.env.SQL_USER || 'iotuser',
  password: process.env.SQL_PASSWORD || 'iot12345',
  database: process.env.SQL_DATABASE_NEWBIZ || 'newbiz',
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  charset: 'utf8mb4',
  supportBigNumbers: true,
  dateStrings: true,
  decimalNumbers: true,
  connectTimeout: 10000
};

// 데이터베이스 연결 정보 로깅
console.log('데이터베이스 연결 정보:', {
  host: process.env.SQL_HOST || 'localhost',
  user: process.env.SQL_USER || 'iotuser',
  database: process.env.SQL_DATABASE_NEWBIZ || 'newbiz',
  // 비밀번호는 보안상 로깅하지 않음
});

// 데이터베이스 풀 생성
export let pool: mysql.Pool;

// 데이터베이스 초기화 함수
export const initializeDatabase = async () => {
  try {
    // 풀 생성
    pool = mysql.createPool(poolConfig);
    
    // 연결 테스트
    const connection = await pool.getConnection();
    console.log('데이터베이스 연결 성공');
    connection.release();
    
    // 테이블 생성
    await pool.execute(`
      CREATE TABLE IF NOT EXISTS book_discussions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_title VARCHAR(255) NOT NULL,
        summary_content TEXT NOT NULL,
        application_content TEXT NOT NULL,
        summary_file_name VARCHAR(255) NOT NULL,
        application_file_name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);
    
    console.log('데이터베이스 초기화 완료');
    
    // 테이블 구조 확인
    try {
      const [rows] = await pool.execute('DESCRIBE book_discussions');
      console.log('book_discussions 테이블 구조:', rows);
    } catch (error) {
      console.error('테이블 구조 확인 오류:', error);
    }
    
  } catch (error) {
    console.error('데이터베이스 초기화 오류:', error);
    throw error;
  }
};

// 테이블 구조 확인
export const checkTableStructure = async () => {
  try {
    const [rows] = await pool.execute('DESCRIBE book_discussions');
    console.log('book_discussions 테이블 구조:', rows);
  } catch (error) {
    console.error('테이블 구조 확인 오류:', error);
  }
};