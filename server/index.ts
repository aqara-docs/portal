import express from 'express';
import cors from 'cors';
import bodyParser from 'body-parser';
import { saveMaterial, saveDiscussion, getBookTitles, getMaterials, getFileNames } from './database';
import OpenAI from 'openai';
import axios from 'axios';
import fs from 'fs';

const app = express();

// CORS 설정 수정
app.use(cors({
  origin: ['http://localhost:3000', 'http://localhost:3001'],  // 허용할 도메인 추가
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// JSON 파싱 미들웨어 설정
app.use(bodyParser.json({ limit: '50mb' }));
app.use(bodyParser.urlencoded({ extended: true, limit: '50mb' }));

// OpenAI 클라이언트 초기화
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// 정적 파일 서빙 설정 추가 (index.ts 상단에)
app.use('/audio', express.static('public/audio'));

app.post('/api/discussions/upload', async (req, res) => {
  try {
    console.log('Received request body:', req.body);

    const { book_title, summary, application } = req.body;
    
    if (!book_title || !summary || !application) {
      throw new Error('필수 데이터가 누락되었습니다.');
    }

    // 요약 파일 저장
    console.log('Saving summary:', {
      book_title,
      fileName: summary.name,
      contentLength: summary.content.length
    });

    const summaryId = await saveMaterial({
      book_title,
      file_name: summary.name,
      content: summary.content,
      type: 'summary'
    });

    // 적용 파일 저장
    console.log('Saving application:', {
      book_title,
      fileName: application.name,
      contentLength: application.content.length
    });

    const applicationId = await saveMaterial({
      book_title,
      file_name: application.name,
      content: application.content,
      type: 'application'
    });

    // 토론 정보 저장
    const discussionDate = new Date().toISOString().split('T')[0];
    const discussionId = await saveDiscussion({
      discussion_date: discussionDate,
      base_material_id: summaryId,
      reading_material_id: applicationId
    });

    console.log('Successfully saved discussion:', {
      discussionId,
      summaryId,
      applicationId
    });

    res.json({
      success: true,
      id: discussionId,
      message: '토론이 성공적으로 저장되었습니다.'
    });
  } catch (error) {
    console.error('Error in /api/discussions/upload:', error);
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : '파일 저장 중 오류가 발생했습니다.'
    });
  }
});

// 책 제목 목록 조회
app.get('/api/books', async (req, res) => {
  console.log('GET /api/books called');
  try {
    const titles = await getBookTitles();
    console.log('Book titles:', titles);
    res.json(titles);
  } catch (error) {
    console.error('책 목록 조회 오류:', error);
    res.status(500).json({ error: '책 목록 조회 중 오류가 발생했습니다.' });
  }
});

// 자료 검색
app.get('/api/materials', async (req, res) => {
  try {
    const { bookTitle, type, fileName } = req.query;
    const materials = await getMaterials(
      bookTitle as string, 
      type as string, 
      fileName as string | undefined
    );
    res.json(materials);
  } catch (error) {
    res.status(500).json({ error: '자료 검색 중 오류가 발생했습니다.' });
  }
});

// 파일 목록 조회 API 수정
app.get('/api/files', async (req, res) => {
  console.log('GET /api/files called with params:', req.query);
  try {
    const { book_title, type } = req.query;
    console.log('Querying files with:', { book_title, type });
    
    const files = await getFileNames(book_title as string, type as string);
    console.log('Files found:', files);
    
    if (files.length === 0) {
      console.log('No files found for:', { book_title, type });
    }
    
    res.json(files);
  } catch (error) {
    console.error('파일 목록 조회 오류:', error);
    res.status(500).json({ error: '파일 목록 조회 중 오류가 발생했습니다.' });
  }
});

// 음성 생성 유틸리티 함수 수정
async function generateSpeech(text: string): Promise<string> {
  try {
    console.log('Generating speech for text:', text.substring(0, 100) + '...');

    // OpenAI TTS API 호출
    console.log('Calling OpenAI TTS API...');
    const response = await openai.audio.speech.create({
      model: "tts-1",
      voice: "alloy",
      input: text
    });

    // 응답을 ArrayBuffer로 변환
    const audioData = await response.arrayBuffer();
    
    // base64로 인코딩
    const base64Audio = Buffer.from(audioData).toString('base64');
    
    // data URL 생성
    const audioUrl = `data:audio/mp3;base64,${base64Audio}`;
    console.log('Audio generated successfully');

    return audioUrl;
  } catch (error) {
    console.error('Error in generateSpeech:', error);
    if (error instanceof Error) {
      console.error('Error details:', error.message, error.stack);
    }
    throw error;
  }
}

// 텍스트 준비 유틸리티 함수 추가
function prepareTextForSpeech(content: string, openingMent?: string, closingMent?: string, type: string = 'AI'): string {
  const defaultOpeningMent = `안녕하세요. ${type} 분석 결과를 말씀드리겠습니다.`;
  const defaultClosingMent = `이상으로 ${type} 분석을 마치겠습니다. 감사합니다.`;

  return `
    ${openingMent || defaultOpeningMent}
    
    ${content}
    
    ${closingMent || defaultClosingMent}
  `.trim();
}

// AI 분석 엔드포인트
app.post('/api/analyze', async (req, res) => {
  try {
    const { content, type, keyword, openingMent } = req.body;
    
    // 기본 멘트 설정 - 클라이언트에서 전달받은 오프닝 멘트 사용
    const defaultOpeningMent = openingMent || (type === '요약' 
      ? "안녕하세요. 독서 토론 요약 분석 결과를 말씀드리겠습니다."
      : "안녕하세요. 적용 보고서 분석 결과를 말씀드리겠습니다.");
    const defaultClosingMent = "이상으로 분석을 마치겠습니다. 감사합니다.";

    console.log('Starting AI analysis...');
    const response = await openai.chat.completions.create({
      model: process.env.MODEL_NAME || "gpt-4o-mini",
      messages: [{
        role: "user",
        content: `
          다음 ${type === '요약' ? '독서 토론 요약' : '적용 보고서'}를 분석해주세요:
          
          ${content}
          
          ${type === '적용' ? `분석 키워드: ${keyword}` : ''}
          
          분석 시 다음 사항을 고려해주세요:
          1. 핵심 내용 요약
          2. 주요 시사점
          3. 실행 가능한 제안
          4. 개선 방향
        `
      }]
    });
    const analysis = response.choices[0]?.message?.content || '';
    console.log('AI analysis completed');

    console.log('Preparing text for speech...');
    const textForSpeech = prepareTextForSpeech(analysis, defaultOpeningMent, defaultClosingMent);
    
    console.log('Generating speech...');
    const audioUrl = await generateSpeech(textForSpeech);
    console.log('Speech generated:', audioUrl);

    res.json({ analysis, audioUrl });
  } catch (error) {
    console.error('AI 분석 오류:', error);
    if (error instanceof Error) {
      console.error('Error details:', error.message, error.stack);
    }
    res.status(500).json({ 
      error: 'AI 분석 중 오류가 발생했습니다.',
      details: error instanceof Error ? error.message : '알 수 없는 오류'
    });
  }
});

// 고급 분석 엔드포인트
app.post('/api/analyze/advanced', async (req, res) => {
  try {
    const { content, keyword } = req.body;
    
    const response = await openai.chat.completions.create({
      model: process.env.MODEL_NAME || "gpt-4o-mini",
      messages: [{
        role: "user",
        content: `
          당신은 비즈니스 전략 보고서 개선 전문가입니다.
          다음 보고서를 ${keyword} 관점에서 분석하고 개선해주세요:
          
          ${content}
          
          다음 형식으로 응답해주세요:
          1. 현재 보고서 분석
          2. 개선 제안
          3. 실행 계획
          4. 기대 효과
        `
      }]
    });
    const improvedReport = response.choices[0]?.message?.content || '';

    const textForSpeech = prepareTextForSpeech(improvedReport, undefined, undefined, '고급');
    const audioUrl = await generateSpeech(textForSpeech);

    res.json({ analysis: improvedReport, improvedReport, audioUrl });
  } catch (error) {
    console.error('고급 분석 오류:', error);
    res.status(500).json({ error: '고급 분석 중 오류가 발생했습니다.' });
  }
});

// 비교 분석 엔드포인트
app.post('/api/analyze/compare', async (req, res) => {
  try {
    const { content, keyword } = req.body;
    
    const response = await openai.chat.completions.create({
      model: process.env.MODEL_NAME || "gpt-4o-mini",
      messages: [{
        role: "user",
        content: `
          당신은 비즈니스 전략 비교 분석 전문가입니다.
          다음 보고서를 ${keyword} 관점에서 다른 기업들과 비교 분석해주세요:
          
          ${content}
        `
      }]
    });
    const comparison = response.choices[0]?.message?.content || '';

    const textForSpeech = prepareTextForSpeech(comparison, undefined, undefined, '비교');
    const audioUrl = await generateSpeech(textForSpeech);

    res.json({ comparison, audioUrl });
  } catch (error) {
    console.error('비교 분석 오류:', error);
    res.status(500).json({ error: '비교 분석 중 오류가 발생했습니다.' });
  }
});

app.listen(3001, () => {
  console.log('Server running on port 3001');
}); 