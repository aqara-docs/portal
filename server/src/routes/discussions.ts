import express from 'express';
import { pool } from '../config/database';
import { RowDataPacket, ResultSetHeader } from 'mysql2';
import path from 'path';
import fs from 'fs';

export const discussionRoutes = express.Router();

// 타입 정의
interface Discussion extends RowDataPacket {
  id: number;
  book_title: string;
  summary_content: string;
  application_content: string;
  summary_file_name: string;
  application_file_name: string;
  created_at: Date;
}

// 에러 타입 정의
interface DatabaseError extends Error {
  code?: string;
  errno?: number;
  sqlMessage?: string;
  sqlState?: string;
}

// 파일 저장 디렉토리 설정 - Streamlit 앱과 동일한 경로 사용
const uploadDir = path.join(__dirname, '../../../uploads/book_discussions');
if (!fs.existsSync(uploadDir)) {
  try {
    fs.mkdirSync(uploadDir, { recursive: true, mode: 0o755 });
    console.log(`업로드 디렉토리 생성 완료: ${uploadDir}`);
  } catch (error) {
    console.error('업로드 디렉토리 생성 오류:', error);
  }
}

// 독서 토론 등록 API 수정
discussionRoutes.post('/', async (req, res) => {
  try {
    console.log('요청 본문 키:', Object.keys(req.body));
    console.log('책 제목:', req.body.bookTitle);
    console.log('요약 파일 이름:', req.body.summaryFileName);
    console.log('적용 파일 이름:', req.body.applicationFileName);
    console.log('요약 내용 길이:', req.body.summaryContent?.length || 0);
    console.log('적용 내용 길이:', req.body.applicationContent?.length || 0);
    
    const { 
      bookTitle, 
      summaryContent, 
      applicationContent, 
      summaryFileName, 
      applicationFileName 
    } = req.body;
    
    // 입력 검증
    if (!bookTitle) {
      console.log('책 제목 누락');
      return res.status(400).json({ error: '책 제목을 입력해주세요.' });
    }

    if (!summaryContent || !applicationContent) {
      console.log('파일 내용 누락');
      return res.status(400).json({ error: '파일 내용이 필요합니다.' });
    }

    if (!summaryFileName || !applicationFileName) {
      console.log('파일 이름 누락');
      return res.status(400).json({ error: '파일 이름이 필요합니다.' });
    }

    // 데이터베이스 쿼리 로깅
    console.log('실행할 쿼리:', `
      INSERT INTO book_discussions 
      (book_title, summary_content, application_content, summary_file_name, application_file_name) 
      VALUES (?, ?, ?, ?, ?)
    `);
    
    console.log('쿼리 파라미터:', [
      bookTitle,
      `${summaryContent.substring(0, 50)}...`, // 내용이 너무 길어 일부만 로깅
      `${applicationContent.substring(0, 50)}...`,
      summaryFileName,
      applicationFileName
    ]);

    // 데이터베이스에 정보 저장
    const query = `
      INSERT INTO book_discussions 
      (book_title, summary_content, application_content, summary_file_name, application_file_name) 
      VALUES (?, ?, ?, ?, ?)
    `;

    try {
      const [result] = await pool.execute<ResultSetHeader>(query, [
        bookTitle,
        summaryContent,
        applicationContent,
        summaryFileName,
        applicationFileName
      ]);
      
      console.log('쿼리 실행 결과:', result);

      res.status(201).json({ 
        message: '독서 토론이 성공적으로 등록되었습니다.',
        id: result.insertId 
      });
    } catch (dbError) {
      console.error('데이터베이스 쿼리 오류:', dbError);
      return res.status(500).json({ error: `데이터베이스 오류: ${(dbError as Error).message}` });
    }
  } catch (error) {
    console.error('독서 토론 등록 오류:', error);
    res.status(500).json({ error: `서버 오류가 발생했습니다: ${(error as Error).message}` });
  }
});

// 독서 토론 검색 API
discussionRoutes.get('/', async (req, res) => {
  try {
    const { bookTitle } = req.query;
    
    let query = 'SELECT * FROM book_discussions WHERE 1=1';
    const params: any[] = [];

    if (bookTitle) {
      query += ' AND book_title LIKE ?';
      params.push(`%${bookTitle}%`);
    }

    query += ' ORDER BY created_at DESC';

    const [rows] = await pool.execute<RowDataPacket[]>(query, params);

    res.json(rows);
  } catch (error) {
    console.error('독서 토론 검색 오류:', error);
    res.status(500).json({ error: '서버 오류가 발생했습니다.' });
  }
});

// 독서 토론 상세 조회 API
discussionRoutes.get('/:id', async (req, res) => {
  try {
    const { id } = req.params;
    
    const query = 'SELECT * FROM book_discussions WHERE id = ?';
    const [rows] = await pool.execute<RowDataPacket[]>(query, [id]);

    if (rows.length === 0) {
      return res.status(404).json({ error: '해당 독서 토론을 찾을 수 없습니다.' });
    }

    res.json(rows[0]);
  } catch (error) {
    console.error('독서 토론 상세 조회 오류:', error);
    res.status(500).json({ error: '서버 오류가 발생했습니다.' });
  }
}); 