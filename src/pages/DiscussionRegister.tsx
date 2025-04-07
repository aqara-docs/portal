import React, { useState, useRef, useEffect } from 'react';
import styled from '@emotion/styled';
import { useForm } from 'react-hook-form';
import axios from 'axios';
import SimpleDatePicker from '../components/common/SimpleDatePicker';
import { saveMaterial, saveDiscussionWithMaterials } from '../services/api';

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

const ErrorMessage = styled.p`
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 0.5rem;
`;

const SuccessMessage = styled.div`
  background-color: #10b981;
  color: white;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
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

// 파일 업로드 관련 스타일
const FileUploadContainer = styled.div`
  border: 2px dashed #e2e8f0;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  margin-bottom: 1.5rem;
  cursor: pointer;
  transition: all 0.3s ease;
  
  &:hover {
    border-color: #3b82f6;
    background-color: #f8fafc;
  }
`;

const FileInput = styled.input`
  display: none;
`;

const FilePreview = styled.div`
  margin-top: 1rem;
  padding: 1rem;
  background-color: #f8fafc;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const FileIcon = styled.div`
  margin-right: 1rem;
  color: #3b82f6;
  font-size: 1.5rem;
`;

const FileInfo = styled.div`
  flex: 1;
  text-align: left;
`;

const FileName = styled.div`
  font-weight: 500;
  margin-bottom: 0.25rem;
`;

const FileSize = styled.div`
  font-size: 0.875rem;
  color: #6b7280;
`;

const RemoveFileButton = styled.button`
  background: none;
  border: none;
  color: #ef4444;
  cursor: pointer;
  font-size: 1.25rem;
`;

// 마크다운 미리보기 컨테이너
const MarkdownPreview = styled.div`
  margin-top: 1rem;
  padding: 1rem;
  background-color: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  max-height: 300px;
  overflow-y: auto;
`;

const UploadPrompt = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
  font-size: 14px;
  cursor: pointer;
`;

interface FormData {
  bookTitle: string;
}

// 책 목록 데이터
const bookOptions = [
  { value: "퍼스널 MBA", label: "퍼스널 MBA" },
  { value: "아주 작은 습관의 힘", label: "아주 작은 습관의 힘" },
  { value: "사피엔스", label: "사피엔스" },
  { value: "생각에 관한 생각", label: "생각에 관한 생각" },
  { value: "데일 카네기의 인간관계론", label: "데일 카네기의 인간관계론" }
];

// 간단한 마크다운 미리보기 컴포넌트
const SimpleMarkdownPreview: React.FC<{ content: string }> = ({ content }) => {
  return (
    <div style={{ whiteSpace: 'pre-wrap' }}>
      {content}
    </div>
  );
};

const DiscussionRegister: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  
  // 파일 업로드 관련 상태
  const [summaryFile, setSummaryFile] = useState<File | null>(null);
  const [applicationFile, setApplicationFile] = useState<File | null>(null);
  const summaryFileInputRef = useRef<HTMLInputElement>(null);
  const applicationFileInputRef = useRef<HTMLInputElement>(null);

  // 파일 내용 상태 추가
  const [summaryContent, setSummaryContent] = useState<string>('');
  const [applicationContent, setApplicationContent] = useState<string>('');

  const { register, handleSubmit, formState: { errors }, reset } = useForm<FormData>({
    defaultValues: {
      bookTitle: "퍼스널 MBA" // 기본값 설정
    }
  });

  // 파일 크기 포맷팅 함수
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' bytes';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  };

  // 파일 업로드 관련 함수
  const handleSummaryFileClick = () => {
    if (summaryFileInputRef.current) {
      summaryFileInputRef.current.click();
    }
  };

  const handleApplicationFileClick = () => {
    if (applicationFileInputRef.current) {
      applicationFileInputRef.current.click();
    }
  };

  // 파일 내용 읽기 함수
  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (event) => {
        if (event.target?.result) {
          resolve(event.target.result as string);
        } else {
          reject(new Error('파일을 읽을 수 없습니다.'));
        }
      };
      reader.onerror = (error) => reject(error);
      reader.readAsText(file);
    });
  };

  // 요약 파일 변경 핸들러 수정
  const handleSummaryFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type === 'text/markdown' || file.name.endsWith('.md')) {
        setSummaryFile(file);
        try {
          const content = await readFileContent(file);
          setSummaryContent(content);
        } catch (error) {
          console.error('파일 읽기 오류:', error);
          alert('파일을 읽는 중 오류가 발생했습니다.');
        }
      } else {
        alert('마크다운(.md) 파일만 업로드 가능합니다.');
      }
    }
  };
  
  // 적용 파일 변경 핸들러 수정
  const handleApplicationFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (file.type === 'text/markdown' || file.name.endsWith('.md')) {
        setApplicationFile(file);
        try {
          const content = await readFileContent(file);
          setApplicationContent(content);
        } catch (error) {
          console.error('파일 읽기 오류:', error);
          alert('파일을 읽는 중 오류가 발생했습니다.');
        }
      } else {
        alert('마크다운(.md) 파일만 업로드 가능합니다.');
      }
    }
  };
  
  // 파일 제거 핸들러 수정
  const removeSummaryFile = () => {
    setSummaryFile(null);
    setSummaryContent('');
    if (summaryFileInputRef.current) {
      summaryFileInputRef.current.value = '';
    }
  };
  
  const removeApplicationFile = () => {
    setApplicationFile(null);
    setApplicationContent('');
    if (applicationFileInputRef.current) {
      applicationFileInputRef.current.value = '';
    }
  };
  
  // 폼 제출 핸들러 수정
  const onSubmit = async (data: FormData) => {
    if (!summaryFile || !summaryContent) {
      alert('독서토론 요약 파일(md)을 업로드해주세요.');
      return;
    }

    if (!applicationFile || !applicationContent) {
      alert('독서토론 적용 파일(md)을 업로드해주세요.');
      return;
    }

    setLoading(true);
    try {
      // JSON 형식으로 데이터 전송
      const requestData = {
        book_title: data.bookTitle,
        summary: {
          name: summaryFile.name,
          content: summaryContent
        },
        application: {
          name: applicationFile.name,
          content: applicationContent
        }
      };

      const response = await axios.post('http://localhost:3001/api/discussions/upload', requestData, {
        headers: {
          'Content-Type': 'application/json',
        }
      });

      console.log('Server response:', response); // 디버깅용 로그

      if (response.data.success) {
        setSuccess(true);
        reset();
        setSummaryFile(null);
        setApplicationFile(null);
        setSummaryContent('');
        setApplicationContent('');
        
        setTimeout(() => {
          setSuccess(false);
        }, 3000);
      } else {
        throw new Error(response.data.error || '파일 저장에 실패했습니다.');
      }
    } catch (error) {
      console.error('API 요청 에러:', error);
      if (axios.isAxiosError(error)) {
        console.error('상세 에러:', {
          message: error.message,
          response: error.response?.data,
          status: error.response?.status,
          config: error.config
        });
        alert(`서버 오류: ${error.response?.data?.error || error.message}`);
      } else {
        alert('파일 저장 중 알 수 없는 오류가 발생했습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageContainer>
      <Title>📚 독서 토론 등록</Title>
      
      {success && (
        <SuccessMessage>
          독서 토론이 성공적으로 등록되었습니다!
        </SuccessMessage>
      )}
      
      <Card>
        <form onSubmit={handleSubmit(onSubmit)}>
          <FormGroup>
            <Label htmlFor="bookTitle">책 제목</Label>
            <Select
              id="bookTitle"
              {...register('bookTitle', { required: '책 제목을 선택해주세요.' })}
            >
              {bookOptions.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            {errors.bookTitle && <ErrorMessage>{errors.bookTitle.message}</ErrorMessage>}
          </FormGroup>
          
          <FormGroup>
            <Label>독서토론 요약 파일 (md)</Label>
            <FileUploadContainer onClick={handleSummaryFileClick}>
              <FileInput 
                type="file" 
                ref={summaryFileInputRef} 
                onChange={handleSummaryFileChange}
                accept=".md"
              />
              {!summaryFile ? (
                <>
                  <div>Drag and drop file here</div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: '0.5rem' }}>
                    Limit 200MB per file • MD
                  </div>
                </>
              ) : (
                <FilePreview>
                  <FileIcon>📄</FileIcon>
                  <FileInfo>
                    <FileName>{summaryFile.name}</FileName>
                    <FileSize>{formatFileSize(summaryFile.size)}</FileSize>
                  </FileInfo>
                  <RemoveFileButton type="button" onClick={(e) => {
                    e.stopPropagation();
                    removeSummaryFile();
                  }}>
                    ×
                  </RemoveFileButton>
                </FilePreview>
              )}
            </FileUploadContainer>
            {summaryContent && (
              <MarkdownPreview>
                <h4>파일 내용 미리보기:</h4>
                <SimpleMarkdownPreview content={summaryContent} />
              </MarkdownPreview>
            )}
          </FormGroup>
          
          <FormGroup>
            <Label>독서토론 적용 파일 (md)</Label>
            <FileUploadContainer onClick={handleApplicationFileClick}>
              <FileInput 
                type="file" 
                ref={applicationFileInputRef} 
                onChange={handleApplicationFileChange}
                accept=".md"
              />
              {!applicationFile ? (
                <UploadPrompt>
                  클릭하여 파일을 업로드하세요
                </UploadPrompt>
              ) : (
                <FilePreview>
                  <FileIcon>📄</FileIcon>
                  <FileInfo>
                    <FileName>{applicationFile?.name}</FileName>
                    <FileSize>{applicationFile?.size ? formatFileSize(applicationFile.size) : ''}</FileSize>
                  </FileInfo>
                  <RemoveFileButton 
                    type="button" 
                    onClick={(e) => {
                      e.stopPropagation();
                      removeApplicationFile();
                    }}
                  >
                    ×
                  </RemoveFileButton>
                </FilePreview>
              )}
            </FileUploadContainer>
            {applicationContent && (
              <MarkdownPreview>
                <h4>파일 내용 미리보기:</h4>
                <SimpleMarkdownPreview content={applicationContent} />
              </MarkdownPreview>
            )}
          </FormGroup>
          
          <Button primary type="submit" disabled={loading}>
            {loading && <LoadingSpinner />}
            {loading ? '등록 중...' : '독서 토론 등록'}
          </Button>
        </form>
      </Card>
    </PageContainer>
  );
};

export default DiscussionRegister; 