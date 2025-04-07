import mysql from 'mysql2/promise';
import dotenv from 'dotenv';
import { RowDataPacket, ResultSetHeader as MySQLResultSetHeader } from 'mysql2/promise';

dotenv.config();

const pool = mysql.createPool({
  host: '127.0.0.1',
  user: process.env.SQL_USER?.replace(/'/g, ''),
  password: process.env.SQL_PASSWORD?.replace(/'/g, ''),
  database: process.env.SQL_DATABASE_NEWBIZ?.replace(/'/g, ''),
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

// 추가 타입 정의
interface ResultSetHeader extends MySQLResultSetHeader {
  insertId: number;
  affectedRows: number;
  fieldCount: number;
  info: string;
  serverStatus: number;
  warningStatus: number;
  changedRows: number;
}

interface SaveMaterialParams {
  book_title: string;
  file_name: string;
  content: string;
  type: string;
}

interface SaveDiscussionParams {
  discussion_date: string;
  base_material_id: number;
  reading_material_id: number;
}

// 타입 매핑 상수 추가
const TYPE_MAPPING = {
  '요약': 'summary',
  '적용': 'application',
  'summary': '요약',
  'application': '적용'
} as const;

// saveMaterial 함수 수정
export const saveMaterial = async ({
  book_title,
  file_name,
  content,
  type
}: SaveMaterialParams): Promise<number> => {
  const connection = await pool.getConnection();
  try {
    // 클라이언트 타입을 DB 타입으로 변환
    const dbType = TYPE_MAPPING[type as keyof typeof TYPE_MAPPING] || type;
    console.log('Saving material with type:', { clientType: type, dbType });

    const [result] = await connection.execute<ResultSetHeader>(
      `INSERT INTO reading_materials (book_title, file_name, content, type)
       VALUES (?, ?, ?, ?)`,
      [book_title, file_name, content, dbType]
    );
    return result.insertId;
  } finally {
    connection.release();
  }
};

// saveDiscussion 함수 수정
export const saveDiscussion = async ({
  discussion_date,
  base_material_id,
  reading_material_id
}: SaveDiscussionParams): Promise<number> => {
  const connection = await pool.getConnection();
  try {
    const [result] = await connection.execute<ResultSetHeader>(
      `INSERT INTO reading_discussions (discussion_date, base_material_id, reading_material_id)
       VALUES (?, ?, ?)`,
      [discussion_date, base_material_id, reading_material_id]
    );
    return result.insertId;
  } finally {
    connection.release();
  }
};

// 연결 테스트 함수 추가
const testConnection = async () => {
  try {
    const connection = await pool.getConnection();
    console.log('Database connection successful');
    connection.release();
  } catch (error) {
    console.error('Database connection failed:', error);
    throw error;
  }
};

// 서버 시작 시 연결 테스트
testConnection();

// 타입 정의 수정
interface BookMaterial extends RowDataPacket {
  id: number;
  book_title: string;
  file_name: string;
  content: string;
  type: string;
  created_at: Date;
}

// 자료 검색 함수 수정
export const getMaterials = async (bookTitle: string, type: string, fileName?: string) => {
  const conn = await pool.getConnection();
  try {
    console.log('Querying materials:', { bookTitle, type, fileName });

    // 클라이언트 타입을 DB 타입으로 변환
    const dbType = TYPE_MAPPING[type as keyof typeof TYPE_MAPPING] || type;

    const query = `
      SELECT 
        id,
        book_title,
        file_name,
        content,
        type,
        created_at
      FROM reading_materials
      WHERE book_title = ? 
        AND type = ?
        ${fileName ? 'AND file_name = ?' : ''}
      ORDER BY created_at DESC
    `;

    const params = fileName ? [bookTitle, dbType, fileName] : [bookTitle, dbType];
    const [rows] = await conn.execute<BookMaterial[]>(query, params);

    // DB 타입을 클라이언트 타입으로 변환하여 결과 반환
    const materials = rows.map(row => ({
      id: row.id,
      bookTitle: row.book_title,
      fileName: row.file_name,
      content: row.content,
      type: TYPE_MAPPING[row.type as keyof typeof TYPE_MAPPING] || row.type,
      createdAt: row.created_at
    }));

    return materials;
  } catch (error) {
    console.error('자료 검색 오류:', error);
    throw error;
  } finally {
    conn.release();
  }
};

// 책 제목 목록 조회 함수 수정
export const getBookTitles = async (): Promise<string[]> => {
  const conn = await pool.getConnection();
  try {
    const query = `
      SELECT DISTINCT book_title
      FROM reading_materials
      ORDER BY book_title
    `;
    const [rows] = await conn.execute<BookMaterial[]>(query);
    return rows.map(row => row.book_title);
  } finally {
    conn.release();
  }
};

// 파일 목록 조회 함수 수정
export const getFileNames = async (book_title: string, type: string) => {
  const conn = await pool.getConnection();
  try {
    console.log('DB Query params:', { book_title, type });

    // 클라이언트 타입을 DB 타입으로 변환
    const dbType = TYPE_MAPPING[type as keyof typeof TYPE_MAPPING] || type;
    console.log('Converted type:', { clientType: type, dbType });

    // 먼저 전체 데이터 확인
    const checkQuery = `
      SELECT book_title, type, COUNT(*) as count 
      FROM reading_materials 
      GROUP BY book_title, type
    `;
    const [counts] = await conn.execute<RowDataPacket[]>(checkQuery);
    console.log('Available data in DB:', counts);

    // 실제 파일 목록 쿼리
    const query = `
      SELECT 
        id,
        book_title,
        file_name,
        content,
        type,
        created_at,
        updated_at
      FROM reading_materials
      WHERE book_title = ? 
        AND type = ?
      ORDER BY created_at DESC
    `;

    const [rows] = await conn.execute<RowDataPacket[]>(query, [book_title, dbType]);
    console.log('Query result:', rows);

    // 결과 데이터 가공 - DB 타입을 클라이언트 타입으로 변환
    const files = rows.map(row => ({
      id: row.id,
      fileName: row.file_name,
      content: row.content,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      type: TYPE_MAPPING[row.type as keyof typeof TYPE_MAPPING] || row.type,
      bookTitle: row.book_title
    }));

    return files;
  } catch (error) {
    console.error('파일 목록 조회 오류:', error);
    throw error;
  } finally {
    conn.release();
  }
};

// 테스트 데이터 추가 함수 수정
export const insertTestData = async () => {
  const conn = await pool.getConnection();
  try {
    // 기존 데이터 확인
    const [existing] = await conn.execute<RowDataPacket[]>(
      'SELECT COUNT(*) as count FROM reading_materials WHERE book_title = ?',
      ['퍼스널 MBA']
    );

    if (existing[0].count === 0) {
      console.log('Inserting test data...');
      
      // DB 타입으로 변환하여 테스트 데이터 추가
      await conn.execute(`
        INSERT INTO reading_materials 
        (book_title, file_name, content, type) 
        VALUES 
        (?, ?, ?, ?),
        (?, ?, ?, ?),
        (?, ?, ?, ?)
      `, [
        '퍼스널 MBA', '1장_요약.md', '# 1장 요약\n\n비즈니스의 기본 원리...', TYPE_MAPPING['요약'],
        '퍼스널 MBA', '2장_요약.md', '# 2장 요약\n\n마케팅의 핵심...', TYPE_MAPPING['요약'],
        '퍼스널 MBA', '1장_적용.md', '# 1장 적용\n\n우리 회사에 적용할 점...', TYPE_MAPPING['적용']
      ]);

      console.log('Test data inserted successfully');
    } else {
      console.log('Test data already exists');
    }
  } catch (error) {
    console.error('Error inserting test data:', error);
    throw error;
  } finally {
    conn.release();
  }
};

// 서버 시작 시 테스트 데이터 추가
testConnection().then(() => {
  insertTestData().catch(console.error);
});