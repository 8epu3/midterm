import datetime
from pathlib import Path
import pandas as pd
import pytest
from unittest.mock import Mock, patch, PropertyMock
from decimal import Decimal
from tempfile import TemporaryDirectory
from app.calculator import Calculator
from app.calculator_repl import calculator_repl
from app.calculator_config import CalculatorConfig
from app.exceptions import OperationError, ValidationError
from app.history import LoggingObserver, AutoSaveObserver
from app.operations import OperationFactory

# Fixture to initialize Calculator with a temporary directory for file paths
@pytest.fixture
def calculator():
    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config = CalculatorConfig(base_dir=temp_path)

        # Patch properties to use the temporary directory paths
        with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
             patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file, \
             patch.object(CalculatorConfig, 'history_dir', new_callable=PropertyMock) as mock_history_dir, \
             patch.object(CalculatorConfig, 'history_file', new_callable=PropertyMock) as mock_history_file:
            
            # Set return values to use paths within the temporary directory
            mock_log_dir.return_value = temp_path / "logs"
            mock_log_file.return_value = temp_path / "logs/calculator.log"
            mock_history_dir.return_value = temp_path / "history"
            mock_history_file.return_value = temp_path / "history/calculator_history.csv"
            
            # Return an instance of Calculator with the mocked config
            yield Calculator(config=config)

# Test Calculator Initialization

def test_calculator_initialization(calculator):
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []
    assert calculator.operation_strategy is None

# Test Logging Setup

@patch('app.calculator.logging.info')
def test_logging_setup(logging_info_mock):
    with patch.object(CalculatorConfig, 'log_dir', new_callable=PropertyMock) as mock_log_dir, \
         patch.object(CalculatorConfig, 'log_file', new_callable=PropertyMock) as mock_log_file:
        mock_log_dir.return_value = Path('/tmp/logs')
        mock_log_file.return_value = Path('/tmp/logs/calculator.log')
        
        # Instantiate calculator to trigger logging
        calculator = Calculator(CalculatorConfig())
        logging_info_mock.assert_any_call("Calculator initialized with configuration")

# Test Adding and Removing Observers

def test_add_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    assert observer in calculator.observers

def test_remove_observer(calculator):
    observer = LoggingObserver()
    calculator.add_observer(observer)
    calculator.remove_observer(observer)
    assert observer not in calculator.observers

# Test Setting Operations

def test_set_operation(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    assert calculator.operation_strategy == operation

# Test Performing Operations

def test_perform_operation_addition(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    result = calculator.perform_operation(2, 3)
    assert result == Decimal('5')

def test_perform_operation_validation_error(calculator):
    calculator.set_operation(OperationFactory.create_operation('add'))
    with pytest.raises(ValidationError):
        calculator.perform_operation('invalid', 3)

def test_perform_operation_operation_error(calculator):
    with pytest.raises(OperationError, match="No operation set"):
        calculator.perform_operation(2, 3)

# Test Undo/Redo Functionality

def test_undo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    assert calculator.history == []

def test_redo(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.undo()
    calculator.redo()
    assert len(calculator.history) == 1

# Test History Management

@patch('app.calculator.pd.DataFrame.to_csv')
def test_save_history(mock_to_csv, calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.save_history()
    mock_to_csv.assert_called_once()

@patch('app.calculator.pd.read_csv')
@patch('app.calculator.Path.exists', return_value=True)
def test_load_history(mock_exists, mock_read_csv, calculator):
    # Mock CSV data to match the expected format in from_dict
    mock_read_csv.return_value = pd.DataFrame({
        'operation': ['Addition'],
        'operand1': ['2'],
        'operand2': ['3'],
        'result': ['5'],
        'timestamp': [datetime.datetime.now().isoformat()]
    })
    
    # Test the load_history functionality
    try:
        calculator.load_history()
        # Verify history length after loading
        assert len(calculator.history) == 1
        # Verify the loaded values
        assert calculator.history[0].operation == "Addition"
        assert calculator.history[0].operand1 == Decimal("2")
        assert calculator.history[0].operand2 == Decimal("3")
        assert calculator.history[0].result == Decimal("5")
    except OperationError:
        pytest.fail("Loading history failed due to OperationError")
        
            
# Test Clearing History

def test_clear_history(calculator):
    operation = OperationFactory.create_operation('add')
    calculator.set_operation(operation)
    calculator.perform_operation(2, 3)
    calculator.clear_history()
    assert calculator.history == []
    assert calculator.undo_stack == []
    assert calculator.redo_stack == []

# Test REPL Commands (using patches for input/output handling)

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("History saved successfully.")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['exit'])
@patch('builtins.print')
def test_calculator_repl_exit_negative(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history', side_effect=Exception("Simulated failure")) as mock_save_history:
        calculator_repl()
        mock_save_history.assert_called_once()
        mock_print.assert_any_call("Warning: Could not save history: Simulated failure")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['help', 'exit'])
@patch('builtins.print')
def test_calculator_repl_help(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nAvailable commands:")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_addition(mock_print, mock_input):
    calculator_repl()
    mock_print.assert_any_call("\nResult: 5")

@patch('builtins.input', side_effect=['history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history_empty(mock_print, mock_input):
    with patch('app.calculator.Calculator.show_history', return_value=[]):
        calculator_repl()
        mock_print.assert_any_call("No calculations in history")

@patch('builtins.input', side_effect=['history', 'exit'])
@patch('builtins.print')
def test_calculator_repl_history_with_entries(mock_print, mock_input):
    with patch('app.calculator.Calculator.show_history', return_value=["Addition(2, 2) = 4", "Multiplication(3, 3) = 9"]):
        calculator_repl()
        mock_print.assert_any_call("\nCalculation History:")
        mock_print.assert_any_call("1. Addition(2, 2) = 4")
        mock_print.assert_any_call("2. Multiplication(3, 3) = 9")

from unittest.mock import patch

@patch('builtins.input', side_effect=['clear', 'exit'])
@patch('builtins.print')
def test_calculator_repl_clear_history(mock_print, mock_input):
    with patch('app.calculator.Calculator.clear_history') as mock_clear_history:
        calculator_repl()
        mock_clear_history.assert_called_once()
        mock_print.assert_any_call("History cleared")

from unittest.mock import patch

@patch('builtins.input', side_effect=['undo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.undo', return_value=True) as mock_undo:
        calculator_repl()
        mock_undo.assert_called_once()
        mock_print.assert_any_call("Operation undone")

@patch('builtins.input', side_effect=['undo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_undo_fail(mock_print, mock_input):
    with patch('app.calculator.Calculator.undo', return_value=False) as mock_undo:
        calculator_repl()
        mock_undo.assert_called_once()
        mock_print.assert_any_call("Nothing to undo")

@patch('builtins.input', side_effect=['redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_redo_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.redo', return_value=True) as mock_undo:
        calculator_repl()
        mock_undo.assert_called_once()
        mock_print.assert_any_call("Operation redone")

@patch('builtins.input', side_effect=['redo', 'exit'])
@patch('builtins.print')
def test_calculator_repl_redo_fail(mock_print, mock_input):
    with patch('app.calculator.Calculator.redo', return_value=False) as mock_undo:
        calculator_repl()
        mock_undo.assert_called_once()
        mock_print.assert_any_call("Nothing to redo")

@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history') as mock_save_history:
        calculator_repl()
        assert mock_save_history.call_count == 2
        mock_print.assert_any_call("History saved successfully")

from unittest.mock import patch

@patch('builtins.input', side_effect=['save', 'exit'])
@patch('builtins.print')
def test_calculator_repl_save_failure(mock_print, mock_input):
    with patch('app.calculator.Calculator.save_history', side_effect=Exception("Simulated error")) as mock_save_history:
        calculator_repl()

        # Don't assert call count since it's called again on 'exit'
        assert mock_save_history.call_count == 2

        mock_print.assert_any_call("Error saving history: Simulated error")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load_failure(mock_print, mock_input):
    with patch('app.calculator.Calculator.load_history', side_effect=Exception("Simulated load error")) as mock_load_history:
        calculator_repl()

        # load_history() may be called again during 'exit', so don't assert call count
        assert mock_load_history.call_count == 2

        mock_print.assert_any_call("Error loading history: Simulated load error")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['load', 'exit'])
@patch('builtins.print')
def test_calculator_repl_load_success(mock_print, mock_input):
    with patch('app.calculator.Calculator.load_history') as mock_load_history:
        calculator_repl()

        # load_history() might be called again on exit, so don't assert exact count
        assert mock_load_history.call_count == 2

        mock_print.assert_any_call("History loaded successfully")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['add', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_cancel(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation') as mock_operation:
        calculator_repl()

        mock_operation.assert_not_called()
        mock_print.assert_any_call("Operation cancelled")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['add', '5', 'cancel', 'exit'])
@patch('builtins.print')
def test_calculator_repl_operation_cancel_second(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation') as mock_operation:
        calculator_repl()

        mock_operation.assert_not_called()
        mock_print.assert_any_call("Operation cancelled")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_validation_or_operation_error(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation', side_effect=ValidationError("Invalid input")) as mock_perform:
        calculator_repl()

        mock_perform.assert_called_once()
        mock_print.assert_any_call("Error: Invalid input")
        mock_print.assert_any_call("Goodbye!")

@patch('builtins.input', side_effect=['add', '2', '3', 'exit'])
@patch('builtins.print')
def test_calculator_repl_unexpected_exception(mock_print, mock_input):
    with patch('app.calculator.Calculator.perform_operation', side_effect=Exception("Something went wrong")) as mock_perform:
        calculator_repl()

        mock_perform.assert_called_once()
        mock_print.assert_any_call("Unexpected error: Something went wrong")
        mock_print.assert_any_call("Goodbye!")
