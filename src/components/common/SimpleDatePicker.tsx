import React from 'react';
import styled from '@emotion/styled';

const DatePickerContainer = styled.div`
  width: 100%;
`;

const DateInput = styled.input`
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

interface SimpleDatePickerProps {
  selected: Date | null;
  onChange: (date: Date) => void;
  placeholderText?: string;
  minDate?: Date | null;
  maxDate?: Date | null;
}

const SimpleDatePicker: React.FC<SimpleDatePickerProps> = ({
  selected,
  onChange,
  placeholderText,
  minDate,
  maxDate
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const date = new Date(e.target.value);
    if (!isNaN(date.getTime())) {
      onChange(date);
    }
  };

  const formatDate = (date: Date | null) => {
    if (!date) return '';
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  };

  const getMinDate = () => {
    if (minDate) {
      return formatDate(minDate);
    }
    return '';
  };

  const getMaxDate = () => {
    if (maxDate) {
      return formatDate(maxDate);
    }
    return '';
  };

  return (
    <DatePickerContainer>
      <DateInput
        type="date"
        value={formatDate(selected)}
        onChange={handleChange}
        placeholder={placeholderText}
        min={getMinDate()}
        max={getMaxDate()}
      />
    </DatePickerContainer>
  );
};

export default SimpleDatePicker; 