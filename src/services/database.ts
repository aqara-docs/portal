import mysql from 'mysql2/promise';
import dotenv from 'dotenv';

dotenv.config();

const pool = mysql.createPool({
  host: process.env.SQL_HOST,
  user: process.env.SQL_USER,
  password: process.env.SQL_PASSWORD,
  database: process.env.SQL_DATABASE_NEWBIZ,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
});

export const executeQuery = async <T>(
  query: string, 
  params?: any[]
): Promise<T> => {
  const connection = await pool.getConnection();
  try {
    const [rows] = await connection.query(query, params);
    return rows as T;
  } finally {
    connection.release();
  }
};

export const saveMaterial = async (
  book_title: string,
  file_name: string,
  content: string,
  type: string
): Promise<number> => {
  const query = `
    INSERT INTO reading_materials (
      book_title, file_name, content, type
    ) VALUES (?, ?, ?, ?)
  `;
  
  const result = await executeQuery<any>(query, [
    book_title,
    file_name,
    content,
    type
  ]);
  
  return result.insertId;
};

export const saveDiscussion = async (
  discussion_date: string,
  base_material_id: number,
  reading_material_id: number
): Promise<number> => {
  const query = `
    INSERT INTO reading_discussions (
      discussion_date,
      base_material_id,
      reading_material_id,
      created_at
    ) VALUES (?, ?, ?, NOW())
  `;
  
  const result = await executeQuery<any>(query, [
    discussion_date,
    base_material_id,
    reading_material_id
  ]);
  
  return result.insertId;
};

export default pool; 