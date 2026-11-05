
#%% Import baseline functions
import pandas as pd
import re
# import math
# from itertools import compress
import sys
import types

#%%

# Own type of exception error, to be raised if function inputs are of wrong type (other than specified by the function)
class WrongFunctionInputType(Exception):
    "Raised when the function input value is of wrong type"
    pass

# Function to automatically check the input types given by a function
# Raises error, if wrong types are passed
def check_function_input_type(func, _locals: dict, exclude_from_check: list[str] = []):
    
    """
    Function to automatically compare function annotations (= variable types) with given function inputs. If variable types differ, error is raised
    Should be put at the beginning of a function. Needs the function and local variables as inputs.
    
    Examples:
    ---------
        >>> def f(x: str, y: dict, z: list, a: tuple, b: None, c: set, d: list[int | float], e: pd.DataFrame) -> list | dict:
                check_function_input_type(f, locals(), exclude_from_check = ["d"])
            
            f("k", {"a": "b"}, [1], ("a",), None, {"a", "b"}, [1, 2.0], pd.DataFrame({"a": ["b"]}))
    
    
    Parameters
    ----------
    func : function
        The function to check (usually the same function where it is applied to)
    
    _locals : dict
        A dictionary of all local variables, using 'locals()'
        
    exclude_from_check : list
        Variables to exclude from check. Default is empty list.

    Raises
    ------
    WrongFunctionInputType
        Raised when the function input value is of wrong type.

    Returns
    -------
    Only performs a type check and does not return anything

    """
    
    # Initialize an empty string
    input_variables_with_errors = ""
    
    # Loop through each function variable and given annotation (e.g., str or int)
    for item in func.__annotations__.keys():
        
        # Skip if check should not be done
        if item in exclude_from_check:
            continue
        
        # Assertion error if variable has parametrized type
        any_parametrized_typemarks = any([hasattr(m, "__origin__") for m in func.__annotations__[item].__args__]) if hasattr(func.__annotations__[item], "__args__") else False
        assert not any_parametrized_typemarks, "Parametrized checks not yet supported --> exclude the variable '" + str(item) + "' from being checked"
        
        # An exception for 'result' parameter
        if _locals.get(item) is None:
            continue
        
        # Check the current variable type with the annotation
        if not isinstance(_locals[item], func.__annotations__[item]):
            
            # If type is different from the annotation, add error information to the string
            input_variables_with_errors += "\nVariable '" + str(item) + "': " + str(type(_locals[item]).__name__) + " --> " + str(func.__annotations__[item].__name__ if not isinstance(func.__annotations__[item], types.UnionType) else func.__annotations__[item])
    
    # If string is not empty, an error has to be raised
    if input_variables_with_errors != "":
        raise WrongFunctionInputType("Some input variables passed for function '" + str(func.__name__) + "' have the wrong instance type and need to be checked:\n\n(VARNAME : CURRENT --> SHOULD)" + input_variables_with_errors)


#%% Function to modify elements of a tuple

def format_values(values: tuple | list,
                  case_insensitive: bool = True,
                  strip: bool = True,
                  remove_special_characters: bool = False,
                  pattern: str = "[()\[\],'\"]") -> tuple:
    
    """
    Function to modify the elements of a tuple.
    Depending on how it is specified in the function input, elements of the tuple:
        - will be written to lowercase
        - edging whitespaces will be stripped
        - special characters (specified by the regex pattern) will be removed

    Parameters
    ----------
    values : tuple[str | tuple] | list[str | tuple]
        The values to be modified. Can either be provied as list or tuple of string and tuple values.
        
    case_insensitive : bool, optional
        If True, all elements are converted to lowercase. The default is True.
    
    strip : bool, optional
        If True, tailing whitespaces of strings are stripped. The default is True.
    
    remove_special_characters : bool, optional
        If True, removes special characters which are specified in the regex pattern. The default is False.
        
    pattern : str, optional
        Pattern to use for removing special characters.

    Raises
    ------
    ValueError
        In case tuple elements are not of type 'tuple' or 'string', raises error.

    Returns
    -------
    values_new : tuple
        The initial tuple with the modified elements is returned.

    """
    
    # Make variable check
    check_function_input_type(format_values, locals())
    
    # Compile pattern
    re_sub = re.compile(pattern)
    
    # Initialize new tuple variable
    values_new = ()
    
    # Loop through each element in the tuple
    for m in values:
        
        # If None is provided, add to tuple and go on
        if m is None:
            values_new += (None,)
            
            # Go on
            continue
        
        # Check if tuple element is of type string
        if isinstance(m, str):
            
            # Write to lowercase, if specified
            if case_insensitive:
                m = m.lower()
            
            # Strip tailing whitespaces, if specified
            if strip:
                m = m.strip()
            
            # Remove special characters, if specified
            if remove_special_characters and re_sub is not None:
                m = re_sub.sub("", m)
            
            # Append
            values_new += (m,)
            
            # Go on
            continue
        
        # Check if tuple element is of type tuple
        if isinstance(m, tuple | list):
            
            # Write to lowercase, if specified
            if case_insensitive:
                m = [n.lower() for n in m]
            
            # Strip tailing whitespaces, if specified
            if strip:
                m = [n.strip() for n in m]
            
            # Remove special characters, if specified
            if remove_special_characters and re_sub is not None:
                m = [re_sub("", n) for n in m]
            
            # Append
            values_new += (tuple(m),)
            
            # Go on
            continue
        
        # Print element
        print(m)
        
        # Raise error if the current type of value can not be catched
        raise ValueError("Instance '" + str(type(m)) + "' not yet catched by function 'format_value'.")
        
    return values_new


    
#%% Define function 'give_back_correct_cas'

def give_back_correct_cas(cas_value: str, return_None: bool = True):
    
    """ Converts a CAS-Nr. into the correct format
    
    Examples:
    ---------
        >>> give_back_correct_cas("000014-51-7")
        "000014-51-7"
    
        >>> give_back_correct_cas("14-51-7")
        "000014-51-7"
        
        >>> give_back_correct_cas("14-51-7", False)
        "000014-51-7"
        
        >>> give_back_correct_cas("No CAS-Nr.", False)
        "No CAS-Nr."
    
    Parameters
    ----------
    cas_value : str
        Any string, which might be a CAS-Nr. (e.g. '52-41-2' or also 'glyphosate').
    
    return_None : bool, optional
        Indicating, whether the original 'cas_value' should be returned or a None, if conversion is unsuccessful. The default is set to True.
        
    Returns
    -------
    str
        If the specific CAS-Nr. format is detected (xxxxxxx(x)-xx-x), a correct CAS-Nr. is given back. Otherwise, either None or the original 'cas_value' is returned depending on how 'return_None' is set.
    """
    
    # Check if cas_value is None, if yes, None is returned. If No, cas_value will be checked if there is a specific CAS-Nr. format.
    if cas_value is None or pd.isnull(cas_value):
        return None
    
    else:
        # Regex pattern with three groups
        pattern_cas = "^([0-9]{1}|[0-9]{2}|[0-9]{3}|[0-9]{4}|[0-9]{5}|[0-9]{6}|[0-9]{7})-([0-9]{2})-([0-9]{1})$"
        x = re.search(pattern_cas, cas_value)
        
        # If no pattern is detected, None is returned
        if x is not None:
            
            # Extract all 3 groups a separate variables
            x1 = x[1]
            x2 = x[2]
            x3 = x[3]
            
            # Group 1 can be either of length 6 or 7. If it is of such length, the cas_value can be returned as it is
            if len(x1) == 7 or len(x1) == 6:
                return cas_value
            
            # If group 1 is of length 5 or lower, add '0' to the beginning of group 1 (for standardization purpose)
            else:
                add_n_zeros = 6 - len(x1)
                return "0"*add_n_zeros + x1 + "-" + x2 + "-" + x3
        else:
            
            if return_None:
                return None
            
            else:
                return cas_value


#%% Define function 'progressbar'

def progressbar(iterable, prefix: str = "", size: int = 40, out = sys.stdout):
    
    """ Generates a generator object which prints a progress bar to the console.
    This function can be wrapped around other functions which are iterables in order to show the progress of the iterables.
    
    Parameters
    ----------
    iterable : iter
        Any type of iterable variable, e.g., list or tuple or other.

    prefix : str, optional
        Any text that should be printed at the beginning of the progress bar. The default is an empty string ("").

    size : (int | float), optional
        The length of the progress bar. In detail, how many '#' are shown. The default is 40.

    out : optional
        The default is sys.stdout.

    Yields
    ------
    item
        Yields item which is used to show progress bar.

    """
    
    # Length of the list to be iterated over
    count = len(iterable)
    
    # start = time.time()
    
    # Define what should be shown --> generating the progress bar
    def show(j):
        
        x = int(size * j / count)
        perc = str(round(j / count * 100, 0)) + "%"
        print(f"\r[{u'#'*x}{(' '*(size-x))}] {perc}", end = '\r', file = out, flush = True)
        
        # # The following lines could be used to also show the elapsed time
        # remaining = ((time.time() - start) / j) * (count - j)
        # mins, sec = divmod(remaining, 60)
        # time_str = f"{int(mins):02}:{sec:05.2f}"
        # print(f"\r{prefix}[{u'█'*x}{('.'*(size-x))}] {j}/{count} Est wait {time_str}", end='\r', file=out, flush=True)
    
    # Loopt through the iterable            
    for i, item in enumerate(iterable):
        
        # Print the prefix, if specified
        if i == 0 and prefix != "":
            print(prefix)
        
        yield item
        show(i + 1)
    
    # Flush console
    print("", flush = True, file = out)


#%% Define function 'flatten'

def flatten(orig_list: list):
    
    """ Function to flatten a nested list or a nested tuple

    Parameters
    ----------
    orig_list : list or tuple
        DA nested list or a nested tuple which should be flattened

    Returns
    -------
    x : list
        Returns a flattened list

    """
    # Raise an error, if the input 'orig_list' is not of type list or type tuple
    check_function_input_type(flatten, locals())
    
    # Make a flat list
    x = [item for sublist in orig_list for item in sublist]
    
    return x 
