import React, { useState, useEffect } from 'react';
import styled from '@emotion/styled';
import axios from 'axios';
import SimpleDatePicker from '../components/common/SimpleDatePicker';
import ReactMarkdown from 'react-markdown';

const PageContainer = styled.div`
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
`;

const Card = styled.div`
  background: white;
  border-radius: 10px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`;

const Title = styled.h1`
  color: #1f2937;
  margin-bottom: 1.5rem;
  font-size: 2rem;
`;

const FormGroup = styled.div`
  margin-bottom: 1.5rem;
`;

const Label = styled.label`
  display: block;
  margin-bottom: 0.5rem;
  color: #4b5563;
  font-weight: 500;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;

  &:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

const Button = styled.button<{ primary?: boolean; loading?: boolean }>`
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: ${props => props.loading ? 'wait' : 'pointer'};
  opacity: ${props => props.loading ? 0.7 : 1};
  transition: all 0.3s ease;
  margin-right: 1rem;
  
  ${props => props.primary ? `
    background: #3b82f6;
    color: white;
    &:hover { background: #2563eb; }
  ` : `
    background: #e2e8f0;
    color: #1f2937;
    &:hover { background: #cbd5e1; }
  `}
`;

const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
`;

const Th = styled.th`
  text-align: left;
  padding: 1rem;
  background-color: #f8fafc;
  border-bottom: 2px solid #e2e8f0;
  color: #4b5563;
`;

const Td = styled.td`
  padding: 1rem;
  border-bottom: 1px solid #e2e8f0;
`;

const Tr = styled.tr`
  &:hover {
    background-color: #f1f5f9;
  }
`;

const DetailsButton = styled.button`
  background: none;
  border: none;
  color: #3b82f6;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  font-size: 0.875rem;
`;

const Modal = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
`;

const ModalContent = styled.div`
  background: white;
  padding: 2rem;
  border-radius: 10px;
  max-width: 800px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
`;

const ModalHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
`;

const CloseButton = styled.button`
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #4b5563;
`;

const ModalTitle = styled.h2`
  margin: 0;
  color: #1f2937;
`;

const DetailItem = styled.div`
  margin-bottom: 1.5rem;
`;

const DetailLabel = styled.h3`
  margin: 0 0 0.5rem 0;
  color: #4b5563;
  font-size: 1rem;
`;

const DetailValue = styled.div`
  color: #1f2937;
`;

const Tag = styled.span`
  background: #e2e8f0;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-right: 0.5rem;
  margin-bottom: 0.5rem;
  display: inline-block;
`;

const NoResults = styled.div`
  text-align: center;
  padding: 2rem;
  color: #6b7280;
`;

const SearchForm = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
`;

const DateRangeContainer = styled.div`
  display: flex;
  gap: 1rem;
  align-items: center;
`;

const LoadingSpinner = styled.div`
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #3498db;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;

  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`;

const Select = styled.select`
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;

  &:focus {
    border-color: #3b82f6;
    outline: none;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
`;

// TYPE_OPTIONS 수정 - DB의 실제 type 값과 매칭되도록
const TYPE_OPTIONS = {
  "요약": "요약",
  "적용": "적용",
  "적용 고급": "적용 고급",
  "적용 비교": "적용 비교"
} as const;

const ANALYSIS_KEYWORDS = [
  "가치 창조",
  "마케팅",
  "세일즈",
  "가치 전달",
  "재무",
  "기타"
] as const;

// 상수 추가
const DEFAULT_BOOK_TITLES = [
  "퍼스널 MBA",
  "초격차",
  "마케팅 불변의 법칙"
] as const;

// 인터페이스 정의
interface Material {
  id: number;
  fileName: string;
  content: string;
  createdAt: string;
  type: keyof typeof TYPE_OPTIONS;
}

interface AIAnalysisResponse {
  analysis: string;
  audioUrl?: string;
}

// AI 분석 결과 표시를 위한 스타일 컴포넌트 추가
const AnalysisContainer = styled.div`
  margin-top: 2rem;
  padding: 1rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background-color: #f8fafc;
`;

const AudioContainer = styled.div`
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 8px;
  background-color: #fff;
`;

// 마크다운 스타일 컴포넌트 추가
const MarkdownContent = styled.div`
  font-size: 1rem;
  line-height: 1.6;
  color: #1f2937;

  h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    font-weight: 600;
  }

  p {
    margin-bottom: 1em;
  }

  ul, ol {
    margin-bottom: 1em;
    padding-left: 2em;
  }

  code {
    background-color: #f3f4f6;
    padding: 0.2em 0.4em;
    border-radius: 3px;
    font-family: monospace;
  }

  blockquote {
    border-left: 4px solid #e5e7eb;
    padding-left: 1em;
    margin-left: 0;
    color: #4b5563;
  }
`;

type AnalysisKeyword = typeof ANALYSIS_KEYWORDS[number];

// 인터페이스에 파일 목록 타입 추가
interface FileOption {
  id: number;
  fileName: string;
  content: string;
  createdAt: string;
}

// axios 인스턴스 생성
const api = axios.create({
  baseURL: 'http://localhost:3001',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true // CORS 설정을 위해 추가
});

const DiscussionSearch: React.FC = () => {
  const [bookTitle, setBookTitle] = useState("퍼스널 MBA");
  const [author, setAuthor] = useState('');
  const [startDate, setStartDate] = useState<Date | null>(null);
  const [endDate, setEndDate] = useState<Date | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [materialType, setMaterialType] = useState("요약");
  const [analysisKeyword, setAnalysisKeyword] = useState<AnalysisKeyword>("가치 창조");
  const [customKeyword, setCustomKeyword] = useState('');
  const [previousTopic, setPreviousTopic] = useState('');
  const [nextTopic, setNextTopic] = useState('');
  const [materials, setMaterials] = useState<Material[]>([]);
  const [bookTitles, setBookTitles] = useState<string[]>([]);
  const [aiAnalysis, setAiAnalysis] = useState<string>('');
  const [audioUrl, setAudioUrl] = useState<string>('');
  const [selectedMaterial, setSelectedMaterial] = useState<Material | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [improvedReport, setImprovedReport] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<string>('');
  const [fileNames, setFileNames] = useState<FileOption[]>([]);
  const [selectedFileName, setSelectedFileName] = useState<string>('');
  const [openingMent, setOpeningMent] = useState<string>('');

  const resetSearch = () => {
    setBookTitle("퍼스널 MBA");
    setMaterialType('요약');
    setAnalysisKeyword("가치 창조");
    setCustomKeyword('');
    setPreviousTopic('');
    setNextTopic('');
    setMaterials([]);
    setAiAnalysis('');
    setAudioUrl('');
    setImprovedReport('');
    setComparisonResult('');
    setSelectedFileName('');
    setFileNames([]);
    setOpeningMent('');
  };

  const viewDetails = (material: Material) => {
    setSelectedMaterial(material);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedMaterial(null);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  // 책 목록 가져오기
  const fetchBookTitles = async () => {
    try {
      const response = await api.get('/api/books');
      let titles = response.data;
      
      // 기본 책 목록과 서버에서 가져온 목록 합치기
      titles = Array.from(new Set([...DEFAULT_BOOK_TITLES, ...titles]));
      
      // "퍼스널 MBA"를 맨 앞으로 이동
      const index = titles.indexOf("퍼스널 MBA");
      if (index > 0) {
        titles = [
          "퍼스널 MBA",
          ...titles.slice(0, index),
          ...titles.slice(index + 1)
        ];
      }
      
      setBookTitles(titles);
      // 기본값으로 "퍼스널 MBA" 선택
      if (!bookTitle) {
        setBookTitle("퍼스널 MBA");
      }
    } catch (error) {
      console.error('책 목록 조회 오류:', error);
      // 오류 발생 시 기본 책 목록 사용
      setBookTitles(DEFAULT_BOOK_TITLES as unknown as string[]);
      setBookTitle("퍼스널 MBA");
    }
  };

  // 컴포넌트 마운트 시 책 목록과 파일 목록 가져오기
  useEffect(() => {
    fetchBookTitles();
    if (bookTitle && materialType) {
      fetchFileNames(bookTitle, materialType);
    }
  }, []); // 의존성 배열 비움

  // 책이나 자료 유형이 변경될 때마다 파일 목록 갱신
  useEffect(() => {
    if (bookTitle && materialType) {
      console.log('Fetching files for:', { bookTitle, materialType });
      fetchFileNames(bookTitle, materialType);
    }
  }, [bookTitle, materialType]); // 의존성 배열에 bookTitle과 materialType 추가

  // 키워드 선택 핸들러 추가
  const handleKeywordChange = (value: string) => {
    setAnalysisKeyword(value as AnalysisKeyword);
    if (value !== "기타") {
      setCustomKeyword("");
    }
  };

  // 키워드 가져오기 함수 추가
  const getKeywordForAnalysis = () => {
    return analysisKeyword === "기타" ? customKeyword : analysisKeyword;
  };

  // AI 분석 요청 함수 수정
  const requestAIAnalysis = async (content: string, type: string) => {
    try {
      setAnalyzing(true);
      
      // 오프닝 멘트 생성
      let defaultOpeningMent = '';
      if (type === '요약') {
        defaultOpeningMent = `안녕하세요. 좋은 아침입니다. 지난번 시간에는 ${previousTopic || '이전 주제'}의 내용으로 독서토론을 진행했습니다. 그럼 오늘 독서 토론 내용을 요약해 드리겠습니다.`;
      } else if (type === '적용') {
        defaultOpeningMent = '유익한 독서 토론이 되셨는지요? 적용 내용에 대한 AI의 평가를 듣고 마치도록 하겠습니다.';
      }

      // 클로징 멘트 생성
      let closingMent = '';
      if (type === '요약') {
        closingMent = '오늘 독서 토론할 내용을 요약해 드렸습니다. 유익한 토론 시간 되세요.';
      } else if (type === '적용') {
        closingMent = `다음 시간에는 ${nextTopic || '다음 주제'}에 대한 독서 토론을 진행할 예정입니다. 즐거운 하루 되세요. 감사합니다.`;
      }

      const response = await api.post('/api/analyze', {
        content,
        type,
        openingMent: openingMent || defaultOpeningMent, // 사용자 입력 또는 기본 멘트 사용
        closingMent,
        keyword: getKeywordForAnalysis()
      });
      
      setAiAnalysis(response.data.analysis);
      if (response.data.audioUrl) {
        setAudioUrl(response.data.audioUrl);
      }
    } catch (error) {
      console.error('AI 분석 오류:', error);
      alert('AI 분석 중 오류가 발생했습니다.');
    } finally {
      setAnalyzing(false);
    }
  };

  // 파일 목록 가져오기 함수 수정
  const fetchFileNames = async (bookTitle: string, type: string) => {
    try {
      console.log('Fetching files for:', { book_title: bookTitle, type });
      
      const response = await api.get('/api/files', {
        params: {
          book_title: bookTitle,
          type
        }
      });
      
      console.log('API Response:', response.data);
      
      if (response.data.length === 0) {
        console.log('No files found');
        alert(`${bookTitle}의 ${type} 파일이 없습니다.`);
      }
      setFileNames(response.data);
    } catch (error) {
      console.error('파일 목록 조회 오류:', error);
      if (axios.isAxiosError(error)) {
        console.error('API Error:', {
          status: error.response?.status,
          data: error.response?.data,
          message: error.message
        });
      }
      alert('파일 목록을 가져오는 중 오류가 발생했습니다.');
    }
  };

  // 검색 함수 수정
  const searchMaterials = async () => {
    if (!bookTitle || !materialType || !selectedFileName) {
      alert('책, 자료 유형, 파일을 모두 선택해주세요.');
      return;
    }

    setLoading(true);
    try {
      const response = await api.get('/api/materials', {
        params: {
          bookTitle,
          type: materialType,
          fileName: selectedFileName
        }
      });

      setMaterials(response.data);
    } catch (error) {
      console.error('자료 검색 오류:', error);
      alert('자료 검색 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 적용 고급 모드 처리 함수 추가
  const handleAdvancedApplication = async (material: Material) => {
    try {
      setAnalyzing(true);
      const response = await api.post('/api/analyze/advanced', {
        content: material.content,
        keyword: getKeywordForAnalysis()
      });
      
      setAiAnalysis(response.data.analysis);
      if (response.data.improvedReport) {
        setImprovedReport(response.data.improvedReport);
      }
    } catch (error) {
      console.error('고급 분석 오류:', error);
      alert('고급 분석 중 오류가 발생했습니다.');
    } finally {
      setAnalyzing(false);
    }
  };

  // 적용 비교 모드 처리 함수 추가
  const handleCompareApplication = async (material: Material) => {
    try {
      setAnalyzing(true);
      const response = await api.post('/api/analyze/compare', {
        content: material.content,
        keyword: getKeywordForAnalysis()
      });
      
      setComparisonResult(response.data.comparison);
    } catch (error) {
      console.error('비교 분석 오류:', error);
      alert('비교 분석 중 오류가 발생했습니다.');
    } finally {
      setAnalyzing(false);
    }
  };

  // 파일 선택 핸들러 추가
  const handleFileSelect = (fileName: string) => {
    setSelectedFileName(fileName);
    if (fileName) {
      searchMaterials(); // 파일 선택 시 자동 검색
    }
  };

  // 검색 버튼 활성화 여부 확인 함수 추가
  const isSearchEnabled = () => {
    return bookTitle && materialType && selectedFileName;
  };

  return (
    <PageContainer>
      <Title>🔍 독서 토론 검색</Title>
      
      <Card>
        <SearchForm>
          <FormGroup>
            <Label htmlFor="bookTitle">책 선택</Label>
            <Select
              id="bookTitle"
              value={bookTitle}
              onChange={(e) => setBookTitle(e.target.value)}
            >
              {bookTitles.map(title => (
                <option key={title} value={title}>{title}</option>
              ))}
            </Select>
          </FormGroup>

          <FormGroup>
            <Label htmlFor="materialType">자료 유형</Label>
            <Select
              id="materialType"
              value={materialType}
              onChange={(e) => {
                setMaterialType(e.target.value);
                // 자료 유형 변경 시 관련 상태 초기화
                setAiAnalysis('');
                setAudioUrl('');
                setPreviousTopic('');
                setNextTopic('');
                setAnalysisKeyword("가치 창조");
                setCustomKeyword('');
                setImprovedReport('');
                setComparisonResult('');
                setSelectedFileName(''); // 파일 선택 초기화 추가
              }}
            >
              {Object.keys(TYPE_OPTIONS).map(label => (
                <option key={label} value={label}>{label}</option>
              ))}
            </Select>
          </FormGroup>

          {materialType === 'summary' && (
            <FormGroup>
              <Label htmlFor="previousTopic">이전 토론 주제</Label>
              <Input
                id="previousTopic"
                value={previousTopic}
                onChange={(e) => setPreviousTopic(e.target.value)}
                placeholder="이전 독서 토론의 주제를 입력해주세요"
              />
            </FormGroup>
          )}

          {materialType === 'application' && (
            <FormGroup>
              <Label htmlFor="nextTopic">다음 토론 주제</Label>
              <Input
                id="nextTopic"
                value={nextTopic}
                onChange={(e) => setNextTopic(e.target.value)}
                placeholder="다음 독서 토론의 주제를 입력해주세요"
              />
            </FormGroup>
          )}

          {['application', 'application_advanced', 'application_compare'].includes(materialType) && (
            <FormGroup>
              <Label htmlFor="analysisKeyword">분석 키워드</Label>
              <Select
                id="analysisKeyword"
                value={analysisKeyword}
                onChange={(e) => handleKeywordChange(e.target.value)}
              >
                {ANALYSIS_KEYWORDS.map(keyword => (
                  <option key={keyword} value={keyword}>{keyword}</option>
                ))}
              </Select>
              {analysisKeyword === "기타" && (
                <Input
                  value={customKeyword}
                  onChange={(e) => setCustomKeyword(e.target.value)}
                  placeholder="키워드를 입력하세요"
                  style={{ marginTop: '0.5rem' }}
                />
              )}
            </FormGroup>
          )}

          <FormGroup>
            <Label htmlFor="fileName">파일 선택</Label>
            <Select
              id="fileName"
              value={selectedFileName}
              onChange={(e) => handleFileSelect(e.target.value)}
            >
              <option value="">파일을 선택하세요</option>
              {fileNames.map(file => (
                <option key={file.id} value={file.fileName}>
                  {`${file.fileName} (${formatDate(file.createdAt)})`}
                </option>
              ))}
            </Select>
          </FormGroup>

          <FormGroup>
            <Label>오프닝 멘트</Label>
            <Input
              type="text"
              value={openingMent}
              onChange={(e) => setOpeningMent(e.target.value)}
              placeholder="AI 분석 시작 멘트를 입력하세요"
            />
          </FormGroup>
        </SearchForm>
        
        <div style={{ marginTop: '1rem' }}>
          <Button 
            primary 
            onClick={searchMaterials} 
            disabled={loading || !isSearchEnabled()}
          >
            {loading && <LoadingSpinner />}
            {loading ? '검색 중...' : '검색'}
          </Button>
          <Button onClick={resetSearch}>초기화</Button>
        </div>
      </Card>
      
      <Card>
        <h2>검색 결과</h2>
        {materials.length > 0 ? (
          <div>
            {materials.map((material) => (
              <div key={material.id} style={{ marginBottom: '2rem' }}>
                <h3>{material.fileName}</h3>
                <MarkdownContent>
                  <ReactMarkdown>{material.content}</ReactMarkdown>
                </MarkdownContent>
                <div style={{ marginTop: '1rem', color: '#666' }}>
                  *등록일: {formatDate(material.createdAt)}*
                </div>
                
                {(material.type === '요약' || material.type === '적용') && (
                  <AnalysisContainer>
                    {!aiAnalysis ? (
                      <Button 
                        onClick={() => requestAIAnalysis(material.content, material.type)}
                        disabled={analyzing}
                      >
                        {analyzing ? 'AI 분석 중...' : `${material.type === '요약' ? '🤖 AI 의견 생성' : 'AI 분석'}`}
                      </Button>
                    ) : (
                      <>
                        <h4>{material.type === '요약' ? '💡 AI 의견' : 'AI 분석 결과'}</h4>
                        <MarkdownContent>
                          <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                        </MarkdownContent>
                        {audioUrl && (
                          <AudioContainer>
                            <h4>🔊 음성으로 듣기</h4>
                            <audio controls>
                              <source src={audioUrl} type="audio/mp3" />
                              Your browser does not support the audio element.
                            </audio>
                          </AudioContainer>
                        )}
                      </>
                    )}
                  </AnalysisContainer>
                )}

                {material.type === '적용 고급' && (
                  <AnalysisContainer>
                    {!improvedReport ? (
                      <Button 
                        onClick={() => handleAdvancedApplication(material)}
                        disabled={analyzing}
                      >
                        {analyzing ? '고급 분석 중...' : '고급 분석 시작'}
                      </Button>
                    ) : (
                      <>
                        <h4>개선된 보고서</h4>
                        <MarkdownContent>
                          <ReactMarkdown>{improvedReport}</ReactMarkdown>
                        </MarkdownContent>
                        <Button 
                          onClick={() => {
                            const blob = new Blob([improvedReport], { type: 'text/markdown' });
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${material.fileName.split('.')[0]}_improved.md`;
                            a.click();
                          }}
                        >
                          📥 개선된 보고서 다운로드
                        </Button>
                      </>
                    )}
                  </AnalysisContainer>
                )}

                {material.type === '적용 비교' && (
                  <AnalysisContainer>
                    {!comparisonResult ? (
                      <Button 
                        onClick={() => handleCompareApplication(material)}
                        disabled={analyzing}
                      >
                        {analyzing ? '비교 분석 중...' : '비교 분석 시작'}
                      </Button>
                    ) : (
                      <>
                        <h4>비교 분석 결과</h4>
                        <MarkdownContent>
                          <ReactMarkdown>{comparisonResult}</ReactMarkdown>
                        </MarkdownContent>
                      </>
                    )}
                  </AnalysisContainer>
                )}
              </div>
            ))}
          </div>
        ) : (
          <NoResults>
            {bookTitle ? `${bookTitle}의 ${materialType} 자료가 없습니다.` : '검색할 책을 선택해주세요.'}
          </NoResults>
        )}
      </Card>
      
      {showModal && selectedMaterial && (
        <Modal onClick={(e) => e.target === e.currentTarget && closeModal()}>
          <ModalContent onClick={(e) => e.stopPropagation()}>
            <ModalHeader>
              <ModalTitle>{selectedMaterial.fileName}</ModalTitle>
              <CloseButton onClick={closeModal}>×</CloseButton>
            </ModalHeader>
            
            <DetailItem>
              <DetailLabel>책 제목</DetailLabel>
              <DetailValue>{selectedMaterial.fileName}</DetailValue>
            </DetailItem>
            
            <DetailItem>
              <DetailLabel>작성 날짜</DetailLabel>
              <DetailValue>{formatDate(selectedMaterial.createdAt)}</DetailValue>
            </DetailItem>
            
            <DetailItem>
              <DetailLabel>내용</DetailLabel>
              <DetailValue>
                <MarkdownContent>
                  <ReactMarkdown>{selectedMaterial.content}</ReactMarkdown>
                </MarkdownContent>
              </DetailValue>
            </DetailItem>

            {['application', 'application_advanced'].includes(selectedMaterial.type) && (
              <DetailItem>
                <DetailLabel>AI 분석</DetailLabel>
                {!aiAnalysis ? (
                  <Button 
                    onClick={() => requestAIAnalysis(selectedMaterial.content, selectedMaterial.type)}
                    disabled={analyzing}
                  >
                    {analyzing ? 'AI 분석 중...' : 'AI 분석 시작'}
                  </Button>
                ) : (
                  <>
                    <DetailValue>
                      <MarkdownContent>
                        <ReactMarkdown>{aiAnalysis}</ReactMarkdown>
                      </MarkdownContent>
                      {audioUrl && (
                        <AudioContainer>
                          <h4>🔊 음성으로 듣기</h4>
                          <audio controls>
                            <source src={audioUrl} type="audio/mp3" />
                            Your browser does not support the audio element.
                          </audio>
                        </AudioContainer>
                      )}
                    </DetailValue>
                  </>
                )}
              </DetailItem>
            )}
          </ModalContent>
        </Modal>
      )}
    </PageContainer>
  );
};

export default DiscussionSearch; 