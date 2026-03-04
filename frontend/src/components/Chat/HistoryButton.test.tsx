import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import HistoryButton from './HistoryButton';

// Mock CSS import
jest.mock('./HistoryButton.css', () => ({}));

describe('HistoryButton Component', () => {
  test('renders button with history icon and text', () => {
    render(<HistoryButton />);
    expect(screen.getByText('历史')).toBeInTheDocument();
    // Check for SVG icon
    const svg = document.querySelector('.history-icon');
    expect(svg).toBeInTheDocument();
  });

  test('has correct title attribute', () => {
    render(<HistoryButton />);
    expect(screen.getByTitle('历史会话')).toBeInTheDocument();
  });

  test('has correct aria-label', () => {
    render(<HistoryButton />);
    expect(screen.getByLabelText('历史会话')).toBeInTheDocument();
  });

  test('calls onClick handler when clicked', () => {
    const mockOnClick = jest.fn();
    
    render(<HistoryButton onClick={mockOnClick} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    
    expect(mockOnClick).toHaveBeenCalledTimes(1);
  });

  test('works without onClick prop', () => {
    render(<HistoryButton />);
    
    const button = screen.getByRole('button');
    // Should not throw error when clicked without onClick
    expect(() => fireEvent.click(button)).not.toThrow();
  });

  test('accepts custom className', () => {
    render(<HistoryButton className="custom-class" />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('history-button');
    expect(button).toHaveClass('custom-class');
  });

  test('button has correct base class', () => {
    render(<HistoryButton />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('history-button');
  });

  test('icon has correct class', () => {
    const { container } = render(<HistoryButton />);
    const icon = container.querySelector('.history-icon');
    expect(icon).toBeInTheDocument();
  });

  test('text has correct class', () => {
    const { container } = render(<HistoryButton />);
    const text = container.querySelector('.history-text');
    expect(text).toBeInTheDocument();
  });

  test('button type is button (not submit)', () => {
    render(<HistoryButton />);
    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('type', 'button');
  });

  test('SVG icon has correct viewBox', () => {
    const { container } = render(<HistoryButton />);
    const svg = container.querySelector('.history-icon');
    expect(svg).toHaveAttribute('viewBox', '0 0 24 24');
  });

  test('SVG icon contains clock circle', () => {
    const { container } = render(<HistoryButton />);
    const circle = container.querySelector('circle');
    expect(circle).toBeInTheDocument();
    expect(circle).toHaveAttribute('cx', '12');
    expect(circle).toHaveAttribute('cy', '12');
    expect(circle).toHaveAttribute('r', '10');
  });

  test('SVG icon contains clock hands', () => {
    const { container } = render(<HistoryButton />);
    const polyline = container.querySelector('polyline');
    expect(polyline).toBeInTheDocument();
    expect(polyline).toHaveAttribute('points', '12,6 12,12 16,14');
  });

  test('multiple clicks call onClick multiple times', () => {
    const mockOnClick = jest.fn();
    
    render(<HistoryButton onClick={mockOnClick} />);
    
    const button = screen.getByRole('button');
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    
    expect(mockOnClick).toHaveBeenCalledTimes(3);
  });

  test('renders without className prop', () => {
    render(<HistoryButton />);
    const button = screen.getByRole('button');
    expect(button).toHaveClass('history-button');
    // Filter out empty strings from split result
    const classes = button.className.split(' ').filter(c => c);
    expect(classes).toHaveLength(1);
    expect(classes[0]).toBe('history-button');
  });
});
