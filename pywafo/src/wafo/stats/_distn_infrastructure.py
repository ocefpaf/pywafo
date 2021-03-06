#
# Author:  Travis Oliphant  2002-2011 with contributions from
#          SciPy Developers 2004-2011
#
from __future__ import division, print_function, absolute_import

from scipy._lib.six import string_types, exec_

import sys
import keyword
import re
import inspect
import types
import warnings

from scipy.misc import doccer
from ._distr_params import distcont, distdiscrete

from scipy.special import xlogy, chndtr, gammaln, hyp0f1, comb

# for root finding for discrete distribution ppf, and max likelihood estimation
from scipy import optimize

# for functions of continuous distributions (e.g. moments, entropy, cdf)
from scipy import integrate

# to approximate the pdf of a continuous distribution given its cdf
from scipy.misc import derivative

from numpy import (arange, putmask, ravel, take, ones, sum, shape,
                   product, reshape, zeros, floor, logical_and, log, sqrt, exp,
                   ndarray)

from numpy import (place, any, argsort, argmax, vectorize,
                   asarray, nan, inf, isinf, NINF, empty)

import numpy as np
import numpy.random as mtrand

from ._constants import _EPS, _XMAX
from .estimation import FitDistribution

try:
    from new import instancemethod
except ImportError:
    # Python 3
    def instancemethod(func, obj, cls):
        return types.MethodType(func, obj)


# These are the docstring parts used for substitution in specific
# distribution docstrings

docheaders = {'methods': """\nMethods\n-------\n""",
              'parameters': """\nParameters\n---------\n""",
              'notes': """\nNotes\n-----\n""",
              'examples': """\nExamples\n--------\n"""}

_doc_rvs = """\
``rvs(%(shapes)s, loc=0, scale=1, size=1)``
    Random variates.
"""
_doc_pdf = """\
``pdf(x, %(shapes)s, loc=0, scale=1)``
    Probability density function.
"""
_doc_logpdf = """\
``logpdf(x, %(shapes)s, loc=0, scale=1)``
    Log of the probability density function.
"""
_doc_pmf = """\
``pmf(x, %(shapes)s, loc=0, scale=1)``
    Probability mass function.
"""
_doc_logpmf = """\
``logpmf(x, %(shapes)s, loc=0, scale=1)``
    Log of the probability mass function.
"""
_doc_cdf = """\
``cdf(x, %(shapes)s, loc=0, scale=1)``
    Cumulative density function.
"""
_doc_logcdf = """\
``logcdf(x, %(shapes)s, loc=0, scale=1)``
    Log of the cumulative density function.
"""
_doc_sf = """\
``sf(x, %(shapes)s, loc=0, scale=1)``
    Survival function (1-cdf --- sometimes more accurate).
"""
_doc_logsf = """\
``logsf(x, %(shapes)s, loc=0, scale=1)``
    Log of the survival function.
"""
_doc_ppf = """\
``ppf(q, %(shapes)s, loc=0, scale=1)``
    Percent point function (inverse of cdf --- percentiles).
"""
_doc_isf = """\
``isf(q, %(shapes)s, loc=0, scale=1)``
    Inverse survival function (inverse of sf).
"""
_doc_moment = """\
``moment(n, %(shapes)s, loc=0, scale=1)``
    Non-central moment of order n
"""
_doc_stats = """\
``stats(%(shapes)s, loc=0, scale=1, moments='mv')``
    Mean('m'), variance('v'), skew('s'), and/or kurtosis('k').
"""
_doc_entropy = """\
``entropy(%(shapes)s, loc=0, scale=1)``
    (Differential) entropy of the RV.
"""
_doc_fit = """\
``fit(data, %(shapes)s, loc=0, scale=1)``
    Parameter estimates for generic data.
"""
_doc_expect = """\
``expect(func, %(shapes)s, loc=0, scale=1, lb=None, ub=None, conditional=False, **kwds)``
    Expected value of a function (of one argument) with respect to the distribution.
"""
_doc_expect_discrete = """\
``expect(func, %(shapes)s, loc=0, lb=None, ub=None, conditional=False)``
    Expected value of a function (of one argument) with respect to the distribution.
"""
_doc_median = """\
``median(%(shapes)s, loc=0, scale=1)``
    Median of the distribution.
"""
_doc_mean = """\
``mean(%(shapes)s, loc=0, scale=1)``
    Mean of the distribution.
"""
_doc_var = """\
``var(%(shapes)s, loc=0, scale=1)``
    Variance of the distribution.
"""
_doc_std = """\
``std(%(shapes)s, loc=0, scale=1)``
    Standard deviation of the distribution.
"""
_doc_interval = """\
``interval(alpha, %(shapes)s, loc=0, scale=1)``
    Endpoints of the range that contains alpha percent of the distribution
"""
_doc_allmethods = ''.join([docheaders['methods'], _doc_rvs, _doc_pdf,
                           _doc_logpdf, _doc_cdf, _doc_logcdf, _doc_sf,
                           _doc_logsf, _doc_ppf, _doc_isf, _doc_moment,
                           _doc_stats, _doc_entropy, _doc_fit,
                           _doc_expect, _doc_median,
                           _doc_mean, _doc_var, _doc_std, _doc_interval])

# Note that the two lines for %(shapes) are searched for and replaced in
# rv_continuous and rv_discrete - update there if the exact string changes
_doc_default_callparams = """
Parameters
----------
x : array_like
    quantiles
q : array_like
    lower or upper tail probability
%(shapes)s : array_like
    shape parameters
loc : array_like, optional
    location parameter (default=0)
scale : array_like, optional
    scale parameter (default=1)
size : int or tuple of ints, optional
    shape of random variates (default computed from input arguments )
moments : str, optional
    composed of letters ['mvsk'] specifying which moments to compute where
    'm' = mean, 'v' = variance, 's' = (Fisher's) skew and
    'k' = (Fisher's) kurtosis.
    Default is 'mv'.
"""
_doc_default_longsummary = """\
Continuous random variables are defined from a standard form and may
require some shape parameters to complete its specification.  Any
optional keyword parameters can be passed to the methods of the RV
object as given below:
"""
_doc_default_frozen_note = """
Alternatively, the object may be called (as a function) to fix the shape,
location, and scale parameters returning a "frozen" continuous RV object:

rv = %(name)s(%(shapes)s, loc=0, scale=1)
    - Frozen RV object with the same methods but holding the given shape,
      location, and scale fixed.
"""
_doc_default_example = """\
Examples
--------
>>> from wafo.stats import %(name)s
>>> import matplotlib.pyplot as plt
>>> fig, ax = plt.subplots(1, 1)

Calculate a few first moments:

%(set_vals_stmt)s
>>> mean, var, skew, kurt = %(name)s.stats(%(shapes)s, moments='mvsk')

Display the probability density function (``pdf``):

>>> x = np.linspace(%(name)s.ppf(0.01, %(shapes)s),
...               %(name)s.ppf(0.99, %(shapes)s), 100)
>>> ax.plot(x, %(name)s.pdf(x, %(shapes)s),
...          'r-', lw=5, alpha=0.6, label='%(name)s pdf')

Alternatively, freeze the distribution and display the frozen pdf:

>>> rv = %(name)s(%(shapes)s)
>>> ax.plot(x, rv.pdf(x), 'k-', lw=2, label='frozen pdf')

Check accuracy of ``cdf`` and ``ppf``:

>>> vals = %(name)s.ppf([0.001, 0.5, 0.999], %(shapes)s)
>>> np.allclose([0.001, 0.5, 0.999], %(name)s.cdf(vals, %(shapes)s))
True

Generate random numbers:

>>> r = %(name)s.rvs(%(shapes)s, size=1000)

And compare the histogram:

>>> ax.hist(r, normed=True, histtype='stepfilled', alpha=0.2)
>>> ax.legend(loc='best', frameon=False)
>>> plt.show()

Compare ML and MPS method
>>> phat = %(name)s.fit2(R, method='ml');
>>> phat.plotfitsummary();  plt.figure(plt.gcf().number+1)
>>> phat2 = %(name)s.fit2(R, method='mps')
>>> phat2.plotfitsummary(); plt.figure(plt.gcf().number+1)

Fix loc=0 and estimate shapes and scale
>>> phat3 = %(name)s.fit2(R, scale=1, floc=0, method='mps')
>>> phat3.plotfitsummary(); plt.figure(plt.gcf().number+1)

Accurate confidence interval with profile loglikelihood
>>> lp = phat3.profile()
>>> lp.plot()
>>> pci = lp.get_bounds()

"""

_doc_default = ''.join([_doc_default_longsummary,
                        _doc_allmethods,
                        _doc_default_callparams,
                        _doc_default_frozen_note,
                        _doc_default_example])

_doc_default_before_notes = ''.join([_doc_default_longsummary,
                                     _doc_allmethods,
                                     _doc_default_callparams,
                                     _doc_default_frozen_note])

docdict = {
    'rvs': _doc_rvs,
    'pdf': _doc_pdf,
    'logpdf': _doc_logpdf,
    'cdf': _doc_cdf,
    'logcdf': _doc_logcdf,
    'sf': _doc_sf,
    'logsf': _doc_logsf,
    'ppf': _doc_ppf,
    'isf': _doc_isf,
    'stats': _doc_stats,
    'entropy': _doc_entropy,
    'fit': _doc_fit,
    'moment': _doc_moment,
    'expect': _doc_expect,
    'interval': _doc_interval,
    'mean': _doc_mean,
    'std': _doc_std,
    'var': _doc_var,
    'median': _doc_median,
    'allmethods': _doc_allmethods,
    'callparams': _doc_default_callparams,
    'longsummary': _doc_default_longsummary,
    'frozennote': _doc_default_frozen_note,
    'example': _doc_default_example,
    'default': _doc_default,
    'before_notes': _doc_default_before_notes
}

# Reuse common content between continuous and discrete docs, change some
# minor bits.
docdict_discrete = docdict.copy()

docdict_discrete['pmf'] = _doc_pmf
docdict_discrete['logpmf'] = _doc_logpmf
docdict_discrete['expect'] = _doc_expect_discrete
_doc_disc_methods = ['rvs', 'pmf', 'logpmf', 'cdf', 'logcdf', 'sf', 'logsf',
                     'ppf', 'isf', 'stats', 'entropy', 'expect', 'median',
                     'mean', 'var', 'std', 'interval',
                     'fit']
for obj in _doc_disc_methods:
    docdict_discrete[obj] = docdict_discrete[obj].replace(', scale=1', '')
docdict_discrete.pop('pdf')
docdict_discrete.pop('logpdf')

_doc_allmethods = ''.join([docdict_discrete[obj] for obj in _doc_disc_methods])
docdict_discrete['allmethods'] = docheaders['methods'] + _doc_allmethods

docdict_discrete['longsummary'] = _doc_default_longsummary.replace(
    'Continuous', 'Discrete')
_doc_default_frozen_note = """
Alternatively, the object may be called (as a function) to fix the shape and
location parameters returning a "frozen" discrete RV object:

rv = %(name)s(%(shapes)s, loc=0)
    - Frozen RV object with the same methods but holding the given shape and
      location fixed.
"""
docdict_discrete['frozennote'] = _doc_default_frozen_note

_doc_default_discrete_example = """\
Examples
--------
>>> from wafo.stats import %(name)s
>>> import matplotlib.pyplot as plt
>>> fig, ax = plt.subplots(1, 1)

Calculate a few first moments:

%(set_vals_stmt)s
>>> mean, var, skew, kurt = %(name)s.stats(%(shapes)s, moments='mvsk')

Display the probability mass function (``pmf``):

>>> x = np.arange(%(name)s.ppf(0.01, %(shapes)s),
...               %(name)s.ppf(0.99, %(shapes)s))
>>> ax.plot(x, %(name)s.pmf(x, %(shapes)s), 'bo', ms=8, label='%(name)s pmf')
>>> ax.vlines(x, 0, %(name)s.pmf(x, %(shapes)s), colors='b', lw=5, alpha=0.5)

Alternatively, freeze the distribution and display the frozen ``pmf``:

>>> rv = %(name)s(%(shapes)s)
>>> ax.vlines(x, 0, rv.pmf(x), colors='k', linestyles='-', lw=1,
...         label='frozen pmf')
>>> ax.legend(loc='best', frameon=False)
>>> plt.show()

Check accuracy of ``cdf`` and ``ppf``:

>>> prob = %(name)s.cdf(x, %(shapes)s)
>>> np.allclose(x, %(name)s.ppf(prob, %(shapes)s))
True

Generate random numbers:

>>> r = %(name)s.rvs(%(shapes)s, size=1000)
"""
docdict_discrete['example'] = _doc_default_discrete_example

_doc_default_before_notes = ''.join([docdict_discrete['longsummary'],
                                     docdict_discrete['allmethods'],
                                     docdict_discrete['callparams'],
                                     docdict_discrete['frozennote']])
docdict_discrete['before_notes'] = _doc_default_before_notes

_doc_default_disc = ''.join([docdict_discrete['longsummary'],
                             docdict_discrete['allmethods'],
                             docdict_discrete['frozennote'],
                             docdict_discrete['example']])
docdict_discrete['default'] = _doc_default_disc


# clean up all the separate docstring elements, we do not need them anymore
for obj in [s for s in dir() if s.startswith('_doc_')]:
    exec('del ' + obj)
del obj
try:
    del s
except NameError:
    # in Python 3, loop variables are not visible after the loop
    pass


def _moment(data, n, mu=None):
    if mu is None:
        mu = data.mean()
    return ((data - mu)**n).mean()


def _moment_from_stats(n, mu, mu2, g1, g2, moment_func, args):
    if (n == 0):
        return 1.0
    elif (n == 1):
        if mu is None:
            val = moment_func(1, *args)
        else:
            val = mu
    elif (n == 2):
        if mu2 is None or mu is None:
            val = moment_func(2, *args)
        else:
            val = mu2 + mu*mu
    elif (n == 3):
        if g1 is None or mu2 is None or mu is None:
            val = moment_func(3, *args)
        else:
            mu3 = g1 * np.power(mu2, 1.5)  # 3rd central moment
            val = mu3+3*mu*mu2+mu*mu*mu  # 3rd non-central moment
    elif (n == 4):
        if g1 is None or g2 is None or mu2 is None or mu is None:
            val = moment_func(4, *args)
        else:
            mu4 = (g2+3.0)*(mu2**2.0)  # 4th central moment
            mu3 = g1*np.power(mu2, 1.5)  # 3rd central moment
            val = mu4+4*mu*mu3+6*mu*mu*mu2+mu*mu*mu*mu
    else:
        val = moment_func(n, *args)

    return val


def _skew(data):
    """
    skew is third central moment / variance**(1.5)
    """
    data = np.ravel(data)
    mu = data.mean()
    m2 = ((data - mu)**2).mean()
    m3 = ((data - mu)**3).mean()
    return m3 / np.power(m2, 1.5)


def _kurtosis(data):
    """
    kurtosis is fourth central moment / variance**2 - 3
    """
    data = np.ravel(data)
    mu = data.mean()
    m2 = ((data - mu)**2).mean()
    m4 = ((data - mu)**4).mean()
    return m4 / m2**2 - 3


# Frozen RV class
class rv_frozen_old(object):

    def __init__(self, dist, *args, **kwds):
        self.args = args
        self.kwds = kwds

        # create a new instance
        self.dist = dist.__class__(**dist._ctor_param)

        # a, b may be set in _argcheck, depending on *args, **kwds. Ouch.
        shapes, _, _ = self.dist._parse_args(*args, **kwds)
        self.dist._argcheck(*shapes)

    def pdf(self, x):   # raises AttributeError in frozen discrete distribution
        return self.dist.pdf(x, *self.args, **self.kwds)

    def logpdf(self, x):
        return self.dist.logpdf(x, *self.args, **self.kwds)

    def cdf(self, x):
        return self.dist.cdf(x, *self.args, **self.kwds)

    def logcdf(self, x):
        return self.dist.logcdf(x, *self.args, **self.kwds)

    def ppf(self, q):
        return self.dist.ppf(q, *self.args, **self.kwds)

    def isf(self, q):
        return self.dist.isf(q, *self.args, **self.kwds)

    def rvs(self, size=None):
        kwds = self.kwds.copy()
        kwds.update({'size': size})
        return self.dist.rvs(*self.args, **kwds)

    def sf(self, x):
        return self.dist.sf(x, *self.args, **self.kwds)

    def logsf(self, x):
        return self.dist.logsf(x, *self.args, **self.kwds)

    def stats(self, moments='mv'):
        kwds = self.kwds.copy()
        kwds.update({'moments': moments})
        return self.dist.stats(*self.args, **kwds)

    def median(self):
        return self.dist.median(*self.args, **self.kwds)

    def mean(self):
        return self.dist.mean(*self.args, **self.kwds)

    def var(self):
        return self.dist.var(*self.args, **self.kwds)

    def std(self):
        return self.dist.std(*self.args, **self.kwds)

    def moment(self, n):
        return self.dist.moment(n, *self.args, **self.kwds)

    def entropy(self):
        return self.dist.entropy(*self.args, **self.kwds)

    def pmf(self, k):
        return self.dist.pmf(k, *self.args, **self.kwds)

    def logpmf(self, k):
        return self.dist.logpmf(k, *self.args, **self.kwds)

    def interval(self, alpha):
        return self.dist.interval(alpha, *self.args, **self.kwds)


# Frozen RV class
class rv_frozen(object):
    ''' Frozen continous or discrete 1D Random Variable object (RV)

    Methods
    -------
    RV.rvs(size=1)
        - random variates

    RV.pdf(x)
        - probability density function (continous case)

    RV.pmf(x)
        - probability mass function (discrete case)

    RV.cdf(x)
        - cumulative density function

    RV.sf(x)
        - survival function (1-cdf --- sometimes more accurate)

    RV.ppf(q)
        - percent point function (inverse of cdf --- percentiles)

    RV.isf(q)
        - inverse survival function (inverse of sf)

    RV.stats(moments='mv')
        - mean('m'), variance('v'), skew('s'), and/or kurtosis('k')

    RV.entropy()
        - (differential) entropy of the RV.

    Parameters
    ----------
    x : array-like
        quantiles
    q : array-like
        lower or upper tail probability
    size : int or tuple of ints, optional, keyword
        shape of random variates
    moments : string, optional, keyword
        one or more of 'm' mean, 'v' variance, 's' skewness, 'k' kurtosis
    '''
    def __init__(self, dist, *args, **kwds):
        self.dist = dist
        args, loc, scale = dist._parse_args(*args, **kwds)
        if isinstance(dist, rv_continuous):
            self.par = args + (loc, scale)
        else:  # rv_discrete
            self.par = args + (loc,)

    def pdf(self, x):
        ''' Probability density function at x of the given RV.'''
        return self.dist.pdf(x, *self.par)

    def logpdf(self, x):
        return self.dist.logpdf(x, *self.par)

    def cdf(self, x):
        '''Cumulative distribution function at x of the given RV.'''
        return self.dist.cdf(x, *self.par)

    def logcdf(self, x):
        return self.dist.logcdf(x, *self.par)

    def ppf(self, q):
        '''Percent point function (inverse of cdf) at q of the given RV.'''
        return self.dist.ppf(q, *self.par)

    def isf(self, q):
        '''Inverse survival function at q of the given RV.'''
        return self.dist.isf(q, *self.par)

    def rvs(self, size=None):
        '''Random variates of given type.'''
        kwds = dict(size=size)
        return self.dist.rvs(*self.par, **kwds)

    def sf(self, x):
        '''Survival function (1-cdf) at x of the given RV.'''
        return self.dist.sf(x, *self.par)

    def logsf(self, x):
        return self.dist.logsf(x, *self.par)

    def stats(self, moments='mv'):
        ''' Some statistics of the given RV'''
        kwds = dict(moments=moments)
        return self.dist.stats(*self.par, **kwds)

    def median(self):
        return self.dist.median(*self.par)

    def mean(self):
        return self.dist.mean(*self.par)

    def var(self):
        return self.dist.var(*self.par)

    def std(self):
        return self.dist.std(*self.par)

    def moment(self, n):
        return self.dist.moment(n, *self.par)

    def entropy(self):
        return self.dist.entropy(*self.par)

    def pmf(self, k):
        '''Probability mass function at k of the given RV'''
        return self.dist.pmf(k, *self.par)

    def logpmf(self, k):
        return self.dist.logpmf(k, *self.par)

    def interval(self, alpha):
        return self.dist.interval(alpha, *self.par)



def valarray(shape, value=nan, typecode=None):
    """Return an array of all value.
    """

    out = ones(shape, dtype=bool) * value
    if typecode is not None:
        out = out.astype(typecode)
    if not isinstance(out, ndarray):
        out = asarray(out)
    return out


def _lazywhere(cond, arrays, f, fillvalue=None, f2=None):
    """
    np.where(cond, x, fillvalue) always evaluates x even where cond is False.
    This one only evaluates f(arr1[cond], arr2[cond], ...).
    For example,
    >>> a, b = np.array([1, 2, 3, 4]), np.array([5, 6, 7, 8])
    >>> def f(a, b):
        return a*b
    >>> _lazywhere(a > 2, (a, b), f, np.nan)
    array([ nan,  nan,  21.,  32.])

    Notice it assumes that all `arrays` are of the same shape, or can be
    broadcasted together.

    """
    if fillvalue is None:
        if f2 is None:
            raise ValueError("One of (fillvalue, f2) must be given.")
        else:
            fillvalue = np.nan
    else:
        if f2 is not None:
            raise ValueError("Only one of (fillvalue, f2) can be given.")

    arrays = np.broadcast_arrays(*arrays)
    temp = tuple(np.extract(cond, arr) for arr in arrays)
    out = valarray(shape(arrays[0]), value=fillvalue)
    np.place(out, cond, f(*temp))
    if f2 is not None:
        temp = tuple(np.extract(~cond, arr) for arr in arrays)
        np.place(out, ~cond, f2(*temp))

    return out


# This should be rewritten
def argsreduce(cond, *args):
    """Return the sequence of ravel(args[i]) where ravel(condition) is
    True in 1D.

    Examples
    --------
    >>> import numpy as np
    >>> rand = np.random.random_sample
    >>> A = rand((4, 5))
    >>> B = 2
    >>> C = rand((1, 5))
    >>> cond = np.ones(A.shape)
    >>> [A1, B1, C1] = argsreduce(cond, A, B, C)
    >>> B1.shape
    (20,)
    >>> cond[2,:] = 0
    >>> [A2, B2, C2] = argsreduce(cond, A, B, C)
    >>> B2.shape
    (15,)

    """
    newargs = np.atleast_1d(*args)
    if not isinstance(newargs, list):
        newargs = [newargs, ]
    expand_arr = (cond == cond)
    return [np.extract(cond, arr1 * expand_arr) for arr1 in newargs]


parse_arg_template = """
def _parse_args(self, %(shape_arg_str)s %(locscale_in)s):
    return (%(shape_arg_str)s), %(locscale_out)s

def _parse_args_rvs(self, %(shape_arg_str)s %(locscale_in)s, size=None):
    return (%(shape_arg_str)s), %(locscale_out)s, size

def _parse_args_stats(self, %(shape_arg_str)s %(locscale_in)s, moments='mv'):
    return (%(shape_arg_str)s), %(locscale_out)s, moments
"""


# Both the continuous and discrete distributions depend on ncx2.
# I think the function name ncx2 is an abbreviation for noncentral chi squared.

def _ncx2_log_pdf(x, df, nc):
    a = asarray(df/2.0)
    fac = -nc/2.0 - x/2.0 + (a-1)*log(x) - a*log(2) - gammaln(a)
    return fac + np.nan_to_num(log(hyp0f1(a, nc * x/4.0)))


def _ncx2_pdf(x, df, nc):
    return np.exp(_ncx2_log_pdf(x, df, nc))


def _ncx2_cdf(x, df, nc):
    return chndtr(x, df, nc)


class rv_generic(object):
    """Class which encapsulates common functionality between rv_discrete
    and rv_continuous.

    """
    def __init__(self):
        super(rv_generic, self).__init__()

        # figure out if _stats signature has 'moments' keyword
        sign = inspect.getargspec(self._stats)
        self._stats_has_moments = ((sign[2] is not None) or
                                   ('moments' in sign[0]))

    def _construct_argparser(
            self, meths_to_inspect, locscale_in, locscale_out):
        """Construct the parser for the shape arguments.

        Generates the argument-parsing functions dynamically and attaches
        them to the instance.
        Is supposed to be called in __init__ of a class for each distribution.

        If self.shapes is a non-empty string, interprets it as a
        comma-separated list of shape parameters.

        Otherwise inspects the call signatures of `meths_to_inspect`
        and constructs the argument-parsing functions from these.
        In this case also sets `shapes` and `numargs`.
        """

        if self.shapes:
            # sanitize the user-supplied shapes
            if not isinstance(self.shapes, string_types):
                raise TypeError('shapes must be a string.')

            shapes = self.shapes.replace(',', ' ').split()

            for field in shapes:
                if keyword.iskeyword(field):
                    raise SyntaxError('keywords cannot be used as shapes.')
                if not re.match('^[_a-zA-Z][_a-zA-Z0-9]*$', field):
                    raise SyntaxError(
                        'shapes must be valid python identifiers')
        else:
            # find out the call signatures (_pdf, _cdf etc), deduce shape
            # arguments
            shapes_list = []
            for meth in meths_to_inspect:
                shapes_args = inspect.getargspec(meth)
                shapes_list.append(shapes_args.args)

                # *args or **kwargs are not allowed w/automatic shapes
                # (generic methods have 'self, x' only)
                if len(shapes_args.args) > 2:
                    if shapes_args.varargs is not None:
                        raise TypeError(
                            '*args are not allowed w/out explicit shapes')
                    if shapes_args.keywords is not None:
                        raise TypeError(
                            '**kwds are not allowed w/out explicit shapes')
                    if shapes_args.defaults is not None:
                        raise TypeError('defaults are not allowed for shapes')

            shapes = max(shapes_list, key=lambda x: len(x))
            shapes = shapes[2:]  # remove self, x,

            # make sure the signatures are consistent
            # (generic methods have 'self, x' only)
            for item in shapes_list:
                if len(item) > 2 and item[2:] != shapes:
                    raise TypeError('Shape arguments are inconsistent.')

        # have the arguments, construct the method from template
        shapes_str = ', '.join(shapes) + ', ' if shapes else ''  # NB: not None
        dct = dict(shape_arg_str=shapes_str,
                   locscale_in=locscale_in,
                   locscale_out=locscale_out,
                   )
        ns = {}
        exec_(parse_arg_template % dct, ns)
        # NB: attach to the instance, not class
        for name in ['_parse_args', '_parse_args_stats', '_parse_args_rvs']:
            setattr(self, name,
                    instancemethod(ns[name], self, self.__class__)
                    )

        self.shapes = ', '.join(shapes) if shapes else None
        if not hasattr(self, 'numargs'):
            # allows more general subclassing with *args
            self.numargs = len(shapes)

    def _construct_doc(self, docdict, shapes_vals=None):
        """Construct the instance docstring with string substitutions."""
        tempdict = docdict.copy()
        tempdict['name'] = self.name or 'distname'
        tempdict['shapes'] = self.shapes or ''

        if shapes_vals is None:
            shapes_vals = ()
        vals = ', '.join(str(_) for _ in shapes_vals)
        tempdict['vals'] = vals

        if self.shapes:
            tempdict['set_vals_stmt'] = '>>> %s = %s' % (self.shapes, vals)
        else:
            tempdict['set_vals_stmt'] = ''

        if self.shapes is None:
            # remove shapes from call parameters if there are none
            for item in ['callparams', 'default', 'before_notes']:
                tempdict[item] = tempdict[item].replace(
                    "\n%(shapes)s : array_like\n    shape parameters", "")
        for i in range(2):
            if self.shapes is None:
                # necessary because we use %(shapes)s in two forms (w w/o ", ")
                self.__doc__ = self.__doc__.replace("%(shapes)s, ", "")
            self.__doc__ = doccer.docformat(self.__doc__, tempdict)

        # correct for empty shapes
        self.__doc__ = self.__doc__.replace('(, ', '(').replace(', )', ')')

    def freeze(self, *args, **kwds):
        """Freeze the distribution for the given arguments.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution.  Should include all
            the non-optional arguments, may include ``loc`` and ``scale``.

        Returns
        -------
        rv_frozen : rv_frozen instance
            The frozen distribution.

        """
        return rv_frozen(self, *args, **kwds)

    def __call__(self, *args, **kwds):
        return self.freeze(*args, **kwds)

    # The actual calculation functions (no basic checking need be done)
    # If these are defined, the others won't be looked at.
    # Otherwise, the other set can be defined.
    def _stats(self, *args, **kwds):
        return None, None, None, None

    #  Central moments
    def _munp(self, n, *args):
        # Silence floating point warnings from integration.
        olderr = np.seterr(all='ignore')
        vals = self.generic_moment(n, *args)
        np.seterr(**olderr)
        return vals

    ## These are the methods you must define (standard form functions)
    ## NB: generic _pdf, _logpdf, _cdf are different for
    ## rv_continuous and rv_discrete hence are defined in there
    def _argcheck(self, *args):
        """Default check for correct values on args and keywords.

        Returns condition array of 1's where arguments are correct and
         0's where they are not.

        """
        cond = 1
        for arg in args:
            cond = logical_and(cond, (asarray(arg) > 0))
        return cond

    ##(return 1-d using self._size to get number)
    def _rvs(self, *args):
        ## Use basic inverse cdf algorithm for RV generation as default.
        U = mtrand.sample(self._size)
        Y = self._ppf(U, *args)
        return Y

    def _logcdf(self, x, *args):
        return log(self._cdf(x, *args))

    def _sf(self, x, *args):
        return 1.0-self._cdf(x, *args)

    def _logsf(self, x, *args):
        return log(self._sf(x, *args))

    def _ppf(self, q, *args):
        return self._ppfvec(q, *args)

    def _isf(self, q, *args):
        return self._ppf(1.0-q, *args)  # use correct _ppf for subclasses

    # These are actually called, and should not be overwritten if you
    # want to keep error checking.
    def rvs(self, *args, **kwds):
        """
        Random variates of given type.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).
        scale : array_like, optional
            Scale parameter (default=1).
        size : int or tuple of ints, optional
            Defining number of random variates (default=1).

        Returns
        -------
        rvs : ndarray or scalar
            Random variates of given `size`.

        """
        discrete = kwds.pop('discrete', None)
        args, loc, scale, size = self._parse_args_rvs(*args, **kwds)
        cond = logical_and(self._argcheck(*args), (scale >= 0))
        if not np.all(cond):
            raise ValueError("Domain error in arguments.")

        # self._size is total size of all output values
        self._size = product(size, axis=0)
        if self._size is not None and self._size > 1:
            size = np.array(size, ndmin=1)

        if np.all(scale == 0):
            return loc*ones(size, 'd')

        vals = self._rvs(*args)
        if self._size is not None:
            vals = reshape(vals, size)

        vals = vals * scale + loc

        # Cast to int if discrete
        if discrete:
            if np.isscalar(vals):
                vals = int(vals)
            else:
                vals = vals.astype(int)

        return vals

    def stats(self, *args, **kwds):
        """
        Some statistics of the given RV

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional (discrete RVs only)
            scale parameter (default=1)
        moments : str, optional
            composed of letters ['mvsk'] defining which moments to compute:
            'm' = mean,
            'v' = variance,
            's' = (Fisher's) skew,
            'k' = (Fisher's) kurtosis.
            (default='mv')

        Returns
        -------
        stats : sequence
            of requested moments.

        """
        args, loc, scale, moments = self._parse_args_stats(*args, **kwds)
        # scale = 1 by construction for discrete RVs
        loc, scale = map(asarray, (loc, scale))
        args = tuple(map(asarray, args))
        cond = self._argcheck(*args) & (scale > 0) & (loc == loc)
        output = []
        default = valarray(shape(cond), self.badvalue)

        # Use only entries that are valid in calculation
        if any(cond):
            goodargs = argsreduce(cond, *(args+(scale, loc)))
            scale, loc, goodargs = goodargs[-2], goodargs[-1], goodargs[:-2]

            if self._stats_has_moments:
                mu, mu2, g1, g2 = self._stats(*goodargs,
                                              **{'moments': moments})
            else:
                mu, mu2, g1, g2 = self._stats(*goodargs)
            if g1 is None:
                mu3 = None
            else:
                if mu2 is None:
                    mu2 = self._munp(2, *goodargs)
                # (mu2**1.5) breaks down for nan and inf
                mu3 = g1 * np.power(mu2, 1.5)

            if 'm' in moments:
                if mu is None:
                    mu = self._munp(1, *goodargs)
                out0 = default.copy()
                place(out0, cond, mu * scale + loc)
                output.append(out0)

            if 'v' in moments:
                if mu2 is None:
                    mu2p = self._munp(2, *goodargs)
                    if mu is None:
                        mu = self._munp(1, *goodargs)
                    mu2 = mu2p - mu * mu
                    if np.isinf(mu):
                        #if mean is inf then var is also inf
                        mu2 = np.inf
                out0 = default.copy()
                place(out0, cond, mu2 * scale * scale)
                output.append(out0)

            if 's' in moments:
                if g1 is None:
                    mu3p = self._munp(3, *goodargs)
                    if mu is None:
                        mu = self._munp(1, *goodargs)
                    if mu2 is None:
                        mu2p = self._munp(2, *goodargs)
                        mu2 = mu2p - mu * mu
                    mu3 = mu3p - 3 * mu * mu2 - mu**3
                    g1 = mu3 / np.power(mu2, 1.5)
                out0 = default.copy()
                place(out0, cond, g1)
                output.append(out0)

            if 'k' in moments:
                if g2 is None:
                    mu4p = self._munp(4, *goodargs)
                    if mu is None:
                        mu = self._munp(1, *goodargs)
                    if mu2 is None:
                        mu2p = self._munp(2, *goodargs)
                        mu2 = mu2p - mu * mu
                    if mu3 is None:
                        mu3p = self._munp(3, *goodargs)
                        mu3 = mu3p - 3 * mu * mu2 - mu**3
                    mu4 = mu4p - 4 * mu * mu3 - 6 * mu * mu * mu2 - mu**4
                    g2 = mu4 / mu2**2.0 - 3.0
                out0 = default.copy()
                place(out0, cond, g2)
                output.append(out0)
        else:  # no valid args
            output = []
            for _ in moments:
                out0 = default.copy()
                output.append(out0)

        if len(output) == 1:
            return output[0]
        else:
            return tuple(output)

    def entropy(self, *args, **kwds):
        """
        Differential entropy of the RV.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).
        scale : array_like, optional  (continuous distributions only).
            Scale parameter (default=1).

        Notes
        -----
        Entropy is defined base `e`:

        >>> drv = rv_discrete(values=((0, 1), (0.5, 0.5)))
        >>> np.allclose(drv.entropy(), np.log(2.0))
        True

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        # NB: for discrete distributions scale=1 by construction in _parse_args
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (scale > 0) & (loc == loc)
        output = zeros(shape(cond0), 'd')
        place(output, (1-cond0), self.badvalue)
        goodargs = argsreduce(cond0, *args)
        # I don't know when or why vecentropy got broken when numargs == 0
        # 09.08.2013: is this still relevant? cf check_vecentropy test
        # in tests/test_continuous_basic.py
        if self.numargs == 0:
            place(output, cond0, self._entropy() + log(scale))
        else:
            place(output, cond0, self.vecentropy(*goodargs) + log(scale))
        return output

    def moment(self, n, *args, **kwds):
        """
        n'th order non-central moment of distribution.

        Parameters
        ----------
        n : int, n>=1
            Order of moment.
        arg1, arg2, arg3,... : float
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        kwds : keyword arguments, optional
            These can include "loc" and "scale", as well as other keyword
            arguments relevant for a given distribution.

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        if not (self._argcheck(*args) and (scale > 0)):
            return nan
        if (floor(n) != n):
            raise ValueError("Moment must be an integer.")
        if (n < 0):
            raise ValueError("Moment must be positive.")
        mu, mu2, g1, g2 = None, None, None, None
        if (n > 0) and (n < 5):
            if self._stats_has_moments:
                mdict = {'moments': {1: 'm', 2: 'v', 3: 'vs', 4: 'vk'}[n]}
            else:
                mdict = {}
            mu, mu2, g1, g2 = self._stats(*args, **mdict)
        val = _moment_from_stats(n, mu, mu2, g1, g2, self._munp, args)

        # Convert to transformed  X = L + S*Y
        # E[X^n] = E[(L+S*Y)^n] = L^n sum(comb(n, k)*(S/L)^k E[Y^k], k=0...n)
        if loc == 0:
            return scale**n * val
        else:
            result = 0
            fac = float(scale) / float(loc)
            for k in range(n):
                valk = _moment_from_stats(k, mu, mu2, g1, g2, self._munp, args)
                result += comb(n, k, exact=True)*(fac**k) * valk
            result += fac**n * val
            return result * loc**n

    def median(self, *args, **kwds):
        """
        Median of the distribution.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            Location parameter, Default is 0.
        scale : array_like, optional
            Scale parameter, Default is 1.

        Returns
        -------
        median : float
            The median of the distribution.

        See Also
        --------
        stats.distributions.rv_discrete.ppf
            Inverse of the CDF

        """
        return self.ppf(0.5, *args, **kwds)

    def mean(self, *args, **kwds):
        """
        Mean of the distribution

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        mean : float
            the mean of the distribution
        """
        kwds['moments'] = 'm'
        res = self.stats(*args, **kwds)
        if isinstance(res, ndarray) and res.ndim == 0:
            return res[()]
        return res

    def var(self, *args, **kwds):
        """
        Variance of the distribution

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        var : float
            the variance of the distribution

        """
        kwds['moments'] = 'v'
        res = self.stats(*args, **kwds)
        if isinstance(res, ndarray) and res.ndim == 0:
            return res[()]
        return res

    def std(self, *args, **kwds):
        """
        Standard deviation of the distribution.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        std : float
            standard deviation of the distribution

        """
        kwds['moments'] = 'v'
        res = sqrt(self.stats(*args, **kwds))
        return res

    def interval(self, alpha, *args, **kwds):
        """
        Confidence interval with equal areas around the median.

        Parameters
        ----------
        alpha : array_like of float
            Probability that an rv will be drawn from the returned range.
            Each value should be in the range [0, 1].
        arg1, arg2, ... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            location parameter, Default is 0.
        scale : array_like, optional
            scale parameter, Default is 1.

        Returns
        -------
        a, b : ndarray of float
            end-points of range that contain ``100 * alpha %`` of the rv's
            possible values.

        """
        alpha = asarray(alpha)
        if any((alpha > 1) | (alpha < 0)):
            raise ValueError("alpha must be between 0 and 1 inclusive")
        q1 = (1.0-alpha)/2
        q2 = (1.0+alpha)/2
        a = self.ppf(q1, *args, **kwds)
        b = self.ppf(q2, *args, **kwds)
        return a, b


##  continuous random variables: implement maybe later
##
##  hf  --- Hazard Function (PDF / SF)
##  chf  --- Cumulative hazard function (-log(SF))
##  psf --- Probability sparsity function (reciprocal of the pdf) in
##                units of percent-point-function (as a function of q).
##                Also, the derivative of the percent-point function.

class rv_continuous(rv_generic):
    """
    A generic continuous random variable class meant for subclassing.

    `rv_continuous` is a base class to construct specific distribution classes
    and instances from for continuous random variables. It cannot be used
    directly as a distribution.

    Parameters
    ----------
    momtype : int, optional
        The type of generic moment calculation to use: 0 for pdf, 1 (default)
        for ppf.
    a : float, optional
        Lower bound of the support of the distribution, default is minus
        infinity.
    b : float, optional
        Upper bound of the support of the distribution, default is plus
        infinity.
    xtol : float, optional
        The tolerance for fixed point calculation for generic ppf.
    badvalue : object, optional
        The value in a result arrays that indicates a value that for which
        some argument restriction is violated, default is np.nan.
    name : str, optional
        The name of the instance. This string is used to construct the default
        example for distributions.
    longname : str, optional
        This string is used as part of the first line of the docstring returned
        when a subclass has no docstring of its own. Note: `longname` exists
        for backwards compatibility, do not use for new subclasses.
    shapes : str, optional
        The shape of the distribution. For example ``"m, n"`` for a
        distribution that takes two integers as the two shape arguments for all
        its methods.
    extradoc :  str, optional, deprecated
        This string is used as the last part of the docstring returned when a
        subclass has no docstring of its own. Note: `extradoc` exists for
        backwards compatibility, do not use for new subclasses.

    Methods
    -------
    ``rvs(<shape(s)>, loc=0, scale=1, size=1)``
        random variates

    ``pdf(x, <shape(s)>, loc=0, scale=1)``
        probability density function

    ``logpdf(x, <shape(s)>, loc=0, scale=1)``
        log of the probability density function

    ``cdf(x, <shape(s)>, loc=0, scale=1)``
        cumulative density function

    ``logcdf(x, <shape(s)>, loc=0, scale=1)``
        log of the cumulative density function

    ``sf(x, <shape(s)>, loc=0, scale=1)``
        survival function (1-cdf --- sometimes more accurate)

    ``logsf(x, <shape(s)>, loc=0, scale=1)``
        log of the survival function

    ``ppf(q, <shape(s)>, loc=0, scale=1)``
      percent point function (inverse of cdf --- quantiles)

    ``isf(q, <shape(s)>, loc=0, scale=1)``
        inverse survival function (inverse of sf)

    ``moment(n, <shape(s)>, loc=0, scale=1)``
        non-central n-th moment of the distribution.  May not work for array
        arguments.

    ``stats(<shape(s)>, loc=0, scale=1, moments='mv')``
        mean('m'), variance('v'), skew('s'), and/or kurtosis('k')

    ``entropy(<shape(s)>, loc=0, scale=1)``
        (differential) entropy of the RV.

    ``fit(data, <shape(s)>, loc=0, scale=1)``
        Parameter estimates for generic data

    ``expect(func=None, args=(), loc=0, scale=1, lb=None, ub=None, conditional=False, **kwds)``
        Expected value of a function with respect to the distribution.
        Additional kwd arguments passed to integrate.quad

    ``median(<shape(s)>, loc=0, scale=1)``
        Median of the distribution.

    ``mean(<shape(s)>, loc=0, scale=1)``
        Mean of the distribution.

    ``std(<shape(s)>, loc=0, scale=1)``
        Standard deviation of the distribution.

    ``var(<shape(s)>, loc=0, scale=1)``
        Variance of the distribution.

    ``interval(alpha, <shape(s)>, loc=0, scale=1)``
        Interval that with `alpha` percent probability contains a random
        realization of this distribution.

    ``__call__(<shape(s)>, loc=0, scale=1)``
        Calling a distribution instance creates a frozen RV object with the
        same methods but holding the given shape, location, and scale fixed.
        See Notes section.

    **Parameters for Methods**

    x : array_like
        quantiles
    q : array_like
        lower or upper tail probability
    <shape(s)> : array_like
        shape parameters
    loc : array_like, optional
        location parameter (default=0)
    scale : array_like, optional
        scale parameter (default=1)
    size : int or tuple of ints, optional
        shape of random variates (default computed from input arguments )
    moments : string, optional
        composed of letters ['mvsk'] specifying which moments to compute where
        'm' = mean, 'v' = variance, 's' = (Fisher's) skew and
        'k' = (Fisher's) kurtosis. (default='mv')
    n : int
        order of moment to calculate in method moments

    Notes
    -----

    **Methods that can be overwritten by subclasses**
    ::

      _rvs
      _pdf
      _cdf
      _sf
      _ppf
      _isf
      _stats
      _munp
      _entropy
      _argcheck

    There are additional (internal and private) generic methods that can
    be useful for cross-checking and for debugging, but might work in all
    cases when directly called.

    **Frozen Distribution**

    Alternatively, the object may be called (as a function) to fix the shape,
    location, and scale parameters returning a "frozen" continuous RV object:

    rv = generic(<shape(s)>, loc=0, scale=1)
        frozen RV object with the same methods but holding the given shape,
        location, and scale fixed

    **Subclassing**

    New random variables can be defined by subclassing rv_continuous class
    and re-defining at least the ``_pdf`` or the ``_cdf`` method (normalized
    to location 0 and scale 1) which will be given clean arguments (in between
    a and b) and passing the argument check method.

    If positive argument checking is not correct for your RV
    then you will also need to re-define the ``_argcheck`` method.

    Correct, but potentially slow defaults exist for the remaining
    methods but for speed and/or accuracy you can over-ride::

      _logpdf, _cdf, _logcdf, _ppf, _rvs, _isf, _sf, _logsf

    Rarely would you override ``_isf``, ``_sf`` or ``_logsf``, but you could.

    Statistics are computed using numerical integration by default.
    For speed you can redefine this using ``_stats``:

     - take shape parameters and return mu, mu2, g1, g2
     - If you can't compute one of these, return it as None
     - Can also be defined with a keyword argument ``moments=<str>``,
       where <str> is a string composed of 'm', 'v', 's',
       and/or 'k'.  Only the components appearing in string
       should be computed and returned in the order 'm', 'v',
       's', or 'k'  with missing values returned as None.

    Alternatively, you can override ``_munp``, which takes n and shape
    parameters and returns the nth non-central moment of the distribution.

    A note on ``shapes``: subclasses need not specify them explicitly. In this
    case, the `shapes` will be automatically deduced from the signatures of the
    overridden methods.
    If, for some reason, you prefer to avoid relying on introspection, you can
    specify ``shapes`` explicitly as an argument to the instance constructor.

    Examples
    --------
    To create a new Gaussian distribution, we would do the following::

        class gaussian_gen(rv_continuous):
            "Gaussian distribution"
            def _pdf(self, x):
                ...
            ...

    """

    def __init__(self, momtype=1, a=None, b=None, xtol=1e-14,
                 badvalue=None, name=None, longname=None,
                 shapes=None, extradoc=None):

        super(rv_continuous, self).__init__()

        # save the ctor parameters, cf generic freeze
        self._ctor_param = dict(
            momtype=momtype, a=a, b=b, xtol=xtol,
            badvalue=badvalue, name=name, longname=longname,
            shapes=shapes, extradoc=extradoc)

        if badvalue is None:
            badvalue = nan
        if name is None:
            name = 'Distribution'
        self.badvalue = badvalue
        self.name = name
        self.a = a
        self.b = b
        if a is None:
            self.a = -inf
        if b is None:
            self.b = inf
        self.xtol = xtol
        self._size = 1
        self.moment_type = momtype
        self.shapes = shapes
        self._construct_argparser(meths_to_inspect=[self._pdf, self._cdf],
                                  locscale_in='loc=0, scale=1',
                                  locscale_out='loc, scale')

        # nin correction
        self._ppfvec = vectorize(self._ppf_single, otypes='d')
        self._ppfvec.nin = self.numargs + 1
        self.vecentropy = vectorize(self._entropy, otypes='d')
        self._cdfvec = vectorize(self._cdf_single, otypes='d')
        self._cdfvec.nin = self.numargs + 1

        # backwards compat.  these were removed in 0.14.0, put back but
        # deprecated in 0.14.1:
        self.vecfunc = np.deprecate(self._ppfvec, "vecfunc")
        self.veccdf = np.deprecate(self._cdfvec, "veccdf")

        self.extradoc = extradoc
        if momtype == 0:
            self.generic_moment = vectorize(self._mom0_sc, otypes='d')
        else:
            self.generic_moment = vectorize(self._mom1_sc, otypes='d')
        # Because of the *args argument of _mom0_sc, vectorize cannot count the
        # number of arguments correctly.
        self.generic_moment.nin = self.numargs + 1

        if longname is None:
            if name[0] in ['aeiouAEIOU']:
                hstr = "An "
            else:
                hstr = "A "
            longname = hstr + name

        if sys.flags.optimize < 2:
            # Skip adding docstrings if interpreter is run with -OO
            if self.__doc__ is None:
                self._construct_default_doc(longname=longname,
                                            extradoc=extradoc)
            else:
                dct = dict(distcont)
                self._construct_doc(docdict, dct.get(self.name))

    def _construct_default_doc(self, longname=None, extradoc=None):
        """Construct instance docstring from the default template."""
        if longname is None:
            longname = 'A'
        if extradoc is None:
            extradoc = ''
        if extradoc.startswith('\n\n'):
            extradoc = extradoc[2:]
        self.__doc__ = ''.join(['%s continuous random variable.' % longname,
                                '\n\n%(before_notes)s\n', docheaders['notes'],
                                extradoc, '\n%(example)s'])
        self._construct_doc(docdict)

    def _ppf_to_solve(self, x, q, *args):
        return self.cdf(*(x, )+args)-q

    def _ppf_single(self, q, *args):
        left = right = None
        if self.a > -np.inf:
            left = self.a
        if self.b < np.inf:
            right = self.b

        factor = 10.
        if not left:  # i.e. self.a = -inf
            left = -1.*factor
            while self._ppf_to_solve(left, q, *args) > 0.:
                right = left
                left *= factor
            # left is now such that cdf(left) < q
        if not right:  # i.e. self.b = inf
            right = factor
            while self._ppf_to_solve(right, q, *args) < 0.:
                left = right
                right *= factor
            # right is now such that cdf(right) > q

        return optimize.brentq(self._ppf_to_solve,
                               left, right, args=(q,)+args, xtol=self.xtol)

    # moment from definition
    def _mom_integ0(self, x, m, *args):
        return x**m * self.pdf(x, *args)

    def _mom0_sc(self, m, *args):
        return integrate.quad(self._mom_integ0, self.a, self.b,
                              args=(m,)+args)[0]

    # moment calculated using ppf
    def _mom_integ1(self, q, m, *args):
        return (self.ppf(q, *args))**m

    def _mom1_sc(self, m, *args):
        return integrate.quad(self._mom_integ1, 0, 1, args=(m,)+args)[0]

    def _pdf(self, x, *args):
        return derivative(self._cdf, x, dx=1e-5, args=args, order=5)

    ## Could also define any of these
    def _logpdf(self, x, *args):
        return log(self._pdf(x, *args))

    def _cdf_single(self, x, *args):
        return integrate.quad(self._pdf, self.a, x, args=args)[0]

    def _cdf(self, x, *args):
        return self._cdfvec(x, *args)

    ## generic _argcheck, _logcdf, _sf, _logsf, _ppf, _isf, _rvs are defined
    ## in rv_generic

    def pdf(self, x, *args, **kwds):
        """
        Probability density function at x of the given RV.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        pdf : ndarray
            Probability density function evaluated at x

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = asarray((x-loc)*1.0/scale)
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x >= self.a) & (x <= self.b)
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        putmask(output, (1-cond0)+np.isnan(x), self.badvalue)
        if any(cond):
            goodargs = argsreduce(cond, *((x,)+args+(scale,)))
            scale, goodargs = goodargs[-1], goodargs[:-1]
            place(output, cond, self._pdf(*goodargs) / scale)
        if output.ndim == 0:
            return output[()]
        return output

    def logpdf(self, x, *args, **kwds):
        """
        Log of the probability density function at x of the given RV.

        This uses a more numerically accurate calculation if available.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        logpdf : array_like
            Log of the probability density function evaluated at x

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = asarray((x-loc)*1.0/scale)
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x >= self.a) & (x <= self.b)
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        putmask(output, (1-cond0)+np.isnan(x), self.badvalue)
        if any(cond):
            goodargs = argsreduce(cond, *((x,)+args+(scale,)))
            scale, goodargs = goodargs[-1], goodargs[:-1]
            place(output, cond, self._logpdf(*goodargs) - log(scale))
        if output.ndim == 0:
            return output[()]
        return output

    def cdf(self, x, *args, **kwds):
        """
        Cumulative distribution function of the given RV.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        cdf : ndarray
            Cumulative distribution function evaluated at `x`

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = (x-loc)*1.0/scale
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x > self.a) & (x < self.b)
        cond2 = (x >= self.b) & cond0
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        place(output, (1-cond0)+np.isnan(x), self.badvalue)
        place(output, cond2, 1.0)
        if any(cond):  # call only if at least 1 entry
            goodargs = argsreduce(cond, *((x,)+args))
            place(output, cond, self._cdf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def logcdf(self, x, *args, **kwds):
        """
        Log of the cumulative distribution function at x of the given RV.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        logcdf : array_like
            Log of the cumulative distribution function evaluated at x

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = (x-loc)*1.0/scale
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x > self.a) & (x < self.b)
        cond2 = (x >= self.b) & cond0
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        place(output, (1-cond0)*(cond1 == cond1)+np.isnan(x), self.badvalue)
        place(output, cond2, 0.0)
        if any(cond):  # call only if at least 1 entry
            goodargs = argsreduce(cond, *((x,)+args))
            place(output, cond, self._logcdf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def sf(self, x, *args, **kwds):
        """
        Survival function (1-cdf) at x of the given RV.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        sf : array_like
            Survival function evaluated at x

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = (x-loc)*1.0/scale
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x > self.a) & (x < self.b)
        cond2 = cond0 & (x <= self.a)
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        place(output, (1-cond0)+np.isnan(x), self.badvalue)
        place(output, cond2, 1.0)
        if any(cond):
            goodargs = argsreduce(cond, *((x,)+args))
            place(output, cond, self._sf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def logsf(self, x, *args, **kwds):
        """
        Log of the survival function of the given RV.

        Returns the log of the "survival function," defined as (1 - `cdf`),
        evaluated at `x`.

        Parameters
        ----------
        x : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        logsf : ndarray
            Log of the survival function evaluated at `x`.

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        x, loc, scale = map(asarray, (x, loc, scale))
        args = tuple(map(asarray, args))
        x = (x-loc)*1.0/scale
        cond0 = self._argcheck(*args) & (scale > 0)
        cond1 = (scale > 0) & (x > self.a) & (x < self.b)
        cond2 = cond0 & (x <= self.a)
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        place(output, (1-cond0)+np.isnan(x), self.badvalue)
        place(output, cond2, 0.0)
        if any(cond):
            goodargs = argsreduce(cond, *((x,)+args))
            place(output, cond, self._logsf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def ppf(self, q, *args, **kwds):
        """
        Percent point function (inverse of cdf) at q of the given RV.

        Parameters
        ----------
        q : array_like
            lower tail probability
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        x : array_like
            quantile corresponding to the lower tail probability q.

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        q, loc, scale = map(asarray, (q, loc, scale))
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (scale > 0) & (loc == loc)
        cond1 = (0 < q) & (q < 1)
        cond2 = cond0 & (q == 0)
        cond3 = cond0 & (q == 1)
        cond = cond0 & cond1
        output = valarray(shape(cond), value=self.badvalue)

        lower_bound = self.a * scale + loc
        upper_bound = self.b * scale + loc
        place(output, cond2, argsreduce(cond2, lower_bound)[0])
        place(output, cond3, argsreduce(cond3, upper_bound)[0])

        if any(cond):  # call only if at least 1 entry
            goodargs = argsreduce(cond, *((q,)+args+(scale, loc)))
            scale, loc, goodargs = goodargs[-2], goodargs[-1], goodargs[:-2]
            place(output, cond, self._ppf(*goodargs) * scale + loc)
        if output.ndim == 0:
            return output[()]
        return output

    def isf(self, q, *args, **kwds):
        """
        Inverse survival function at q of the given RV.

        Parameters
        ----------
        q : array_like
            upper tail probability
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            location parameter (default=0)
        scale : array_like, optional
            scale parameter (default=1)

        Returns
        -------
        x : ndarray or scalar
            Quantile corresponding to the upper tail probability q.

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        q, loc, scale = map(asarray, (q, loc, scale))
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (scale > 0) & (loc == loc)
        cond1 = (0 < q) & (q < 1)
        cond2 = cond0 & (q == 1)
        cond3 = cond0 & (q == 0)
        cond = cond0 & cond1
        output = valarray(shape(cond), value=self.badvalue)

        lower_bound = self.a * scale + loc
        upper_bound = self.b * scale + loc
        place(output, cond2, argsreduce(cond2, lower_bound)[0])
        place(output, cond3, argsreduce(cond3, upper_bound)[0])

        if any(cond):
            goodargs = argsreduce(cond, *((q,)+args+(scale, loc)))
            scale, loc, goodargs = goodargs[-2], goodargs[-1], goodargs[:-2]
            place(output, cond, self._isf(*goodargs) * scale + loc)
        if output.ndim == 0:
            return output[()]
        return output

    def link(self, x, logSF, theta, i):
        '''
        Return theta[i] as function of quantile, survival probability and
            theta[j] for j!=i.

        Parameters
        ----------
        x : quantile
        logSF : logarithm of the survival probability
        theta : list
            all distribution parameters including location and scale.

        Returns
        -------
        theta[i] : real scalar
            fixed distribution parameter theta[i] as function of x, logSF and
            theta[j] where j != i.

        LINK is a function connecting the fixed distribution parameter theta[i]
        with the quantile (x) and the survival probability (SF) and the
        remaining free distribution parameters theta[j] for j!=i, i.e.:
            theta[i] = link(x, logSF, theta, i),
        where logSF = log(Prob(X>x; theta)).

        See also
        estimation.Profile
        '''
        return self._link(x, logSF, theta, i)

    def _link(self, x, logSF, theta, i):
        msg = ('Link function not implemented for the %s distribution' %
               self.name)
        raise NotImplementedError(msg)


    def _nnlf(self, x, *args):
        return -sum(self._logpdf(x, *args), axis=0)

    def nnlf(self, theta, x):
        '''Return negative loglikelihood function

        Notes
        -----
        This is ``-sum(log pdf(x, theta), axis=0)`` where theta are the
        parameters (including loc and scale).
        '''
        try:
            loc = theta[-2]
            scale = theta[-1]
            args = tuple(theta[:-2])
        except IndexError:
            raise ValueError("Not enough input arguments.")
        if not self._argcheck(*args) or scale <= 0:
            return inf
        x = asarray((x-loc) / scale)
        cond0 = (x <= self.a) | (self.b <= x)
        if (any(cond0)):
            return inf
        else:
            N = len(x)
            return self._nnlf(x, *args) + N * log(scale)

    def _penalized_nnlf(self, theta, x):
        ''' Return negative loglikelihood function,
        i.e., - sum (log pdf(x, theta), axis=0)
           where theta are the parameters (including loc and scale)
        '''
        try:
            loc = theta[-2]
            scale = theta[-1]
            args = tuple(theta[:-2])
        except IndexError:
            raise ValueError("Not enough input arguments.")
        if not self._argcheck(*args) or scale <= 0:
            return inf
        x = asarray((x-loc) / scale)

        loginf = log(_XMAX)

        if np.isneginf(self.a).all() and np.isinf(self.b).all():
            Nbad = 0
        else:
            cond0 = (x <= self.a) | (self.b <= x)
            Nbad = sum(cond0)
            if Nbad > 0:
                x = argsreduce(~cond0, x)[0]

        N = len(x)
        return self._nnlf(x, *args) + N*log(scale) + Nbad * 100.0 * loginf

    def hessian_nnlf(self, theta, data, eps=None):
        ''' approximate hessian of nnlf where theta are the parameters (including loc and scale)
        '''
        #Nd = len(x)
        np = len(theta)
        # pab 07.01.2001: Always choose the stepsize h so that
        # it is an exactly representable number.
        # This is important when calculating numerical derivatives and is
        #  accomplished by the following.

        if eps == None:
            eps = (_EPS) ** 0.4
        #xmin = floatinfo.machar.xmin
        #myfun = lambda y: max(y,100.0*log(xmin)) #% trick to avoid log of zero
        delta = (eps + 2.0) - 2.0
        delta2 = delta ** 2.0
        # Approximate 1/(nE( (d L(x|theta)/dtheta)^2)) with
        #              1/(d^2 L(theta|x)/dtheta^2)
        # using central differences

        LL = self.nnlf(theta, data)
        H = zeros((np, np))   #%% Hessian matrix
        theta = tuple(theta)
        for ix in xrange(np):
            sparam = list(theta)
            sparam[ix] = theta[ix] + delta
            fp = self.nnlf(sparam, data)
            #fp = sum(myfun(x))

            sparam[ix] = theta[ix] - delta
            fm = self.nnlf(sparam, data)
            #fm = sum(myfun(x))

            H[ix, ix] = (fp - 2 * LL + fm) / delta2
            for iy in range(ix + 1, np):
                sparam[ix] = theta[ix] + delta
                sparam[iy] = theta[iy] + delta
                fpp = self.nnlf(sparam, data)
                #fpp = sum(myfun(x))

                sparam[iy] = theta[iy] - delta
                fpm = self.nnlf(sparam, data)
                #fpm = sum(myfun(x))

                sparam[ix] = theta[ix] - delta
                fmm = self.nnlf(sparam, data)
                #fmm = sum(myfun(x));

                sparam[iy] = theta[iy] + delta
                fmp = self.nnlf(sparam, data)
                #fmp = sum(myfun(x))
                H[ix, iy] = ((fpp + fmm) - (fmp + fpm)) / (4. * delta2)
                H[iy, ix] = H[ix, iy]
                sparam[iy] = theta[iy]

        # invert the Hessian matrix (i.e. invert the observed information number)
        #pcov = -pinv(H);
        return - H

    def nlogps(self, theta, x):
        """ Moran's negative log Product Spacings statistic

            where theta are the parameters (including loc and scale)

            Note the data in x must be sorted

        References
        -----------

        R. C. H. Cheng; N. A. K. Amin (1983)
        "Estimating Parameters in Continuous Univariate Distributions with a
        Shifted Origin.",
        Journal of the Royal Statistical Society. Series B (Methodological),
        Vol. 45, No. 3. (1983), pp. 394-403.

        R. C. H. Cheng; M. A. Stephens (1989)
        "A Goodness-Of-Fit Test Using Moran's Statistic with Estimated
        Parameters", Biometrika, 76, 2, pp 385-392

        Wong, T.S.T. and Li, W.K. (2006)
        "A note on the estimation of extreme value distributions using maximum
        product of spacings.",
        IMS Lecture Notes Monograph Series 2006, Vol. 52, pp. 272-283
        """

        try:
            loc = theta[-2]
            scale = theta[-1]
            args = tuple(theta[:-2])
        except IndexError:
            raise ValueError("Not enough input arguments.")
        if not self._argcheck(*args) or scale <= 0:
            return inf
        x = asarray((x - loc) / scale)
        cond0 = (x <= self.a) | (self.b <= x)
        Nbad = sum(cond0)
        if Nbad > 0:
            x = argsreduce(~cond0, x)[0]

        lowertail = True
        if lowertail:
            prb = np.hstack((0.0, self.cdf(x, *args), 1.0))
            dprb = np.diff(prb)
        else:
            prb = np.hstack((1.0, self.sf(x, *args), 0.0))
            dprb = -np.diff(prb)

        logD = log(dprb)
        dx = np.diff(x, axis=0)
        tie = (dx == 0)
        if any(tie):
            # TODO : implement this method for treating ties in data:
            # Assume measuring error is delta. Then compute
            # yL = F(xi-delta,theta)
            # yU = F(xi+delta,theta)
            # and replace
            # logDj = log((yU-yL)/(r-1)) for j = i+1,i+2,...i+r-1

            # The following is OK when only minimization of T is wanted
            i_tie, = np.nonzero(tie)
            tiedata = x[i_tie]
            logD[i_tie + 1] = log(self._pdf(tiedata, *args)) - log(scale)

        finiteD = np.isfinite(logD)
        nonfiniteD = 1 - finiteD
        Nbad += sum(nonfiniteD, axis=0)
        if Nbad > 0:
            T = -sum(logD[finiteD], axis=0) + 100.0 * log(_XMAX) * Nbad
        else:
            T = -sum(logD, axis=0)  #Moran's negative log product spacing statistic
        return T

    def hessian_nlogps(self, theta, data, eps=None):
        ''' approximate hessian of nlogps where theta are the parameters (including loc and scale)
        '''
        np = len(theta)
        # pab 07.01.2001: Always choose the stepsize h so that
        # it is an exactly representable number.
        # This is important when calculating numerical derivatives and is
        #  accomplished by the following.

        if eps == None:
            eps = (_EPS) ** 0.4
        #xmin = floatinfo.machar.xmin
        #myfun = lambda y: max(y,100.0*log(xmin)) #% trick to avoid log of zero
        delta = (eps + 2.0) - 2.0
        delta2 = delta ** 2.0
        #  Approximate 1/(nE( (d L(x|theta)/dtheta)^2)) with
        #               1/(d^2 L(theta|x)/dtheta^2)
        #    using central differences

        LL = self.nlogps(theta, data)
        H = zeros((np, np))   # Hessian matrix
        theta = tuple(theta)
        for ix in xrange(np):
            sparam = list(theta)
            sparam[ix] = theta[ix] + delta
            fp = self.nlogps(sparam, data)
            #fp = sum(myfun(x))

            sparam[ix] = theta[ix] - delta
            fm = self.nlogps(sparam, data)
            #fm = sum(myfun(x))

            H[ix, ix] = (fp - 2 * LL + fm) / delta2
            for iy in range(ix + 1, np):
                sparam[ix] = theta[ix] + delta
                sparam[iy] = theta[iy] + delta
                fpp = self.nlogps(sparam, data)
                #fpp = sum(myfun(x))

                sparam[iy] = theta[iy] - delta
                fpm = self.nlogps(sparam, data)
                #fpm = sum(myfun(x))

                sparam[ix] = theta[ix] - delta
                fmm = self.nlogps(sparam, data)
                #fmm = sum(myfun(x));

                sparam[iy] = theta[iy] + delta
                fmp = self.nlogps(sparam, data)
                #fmp = sum(myfun(x))
                H[ix, iy] = ((fpp + fmm) - (fmp + fpm)) / (4. * delta2)
                H[iy, ix] = H[ix, iy]
                sparam[iy] = theta[iy];

        # invert the Hessian matrix (i.e. invert the observed information number)
        #pcov = -pinv(H);
        return - H

    # return starting point for fit (shape arguments + loc + scale)
    def _fitstart(self, data, args=None):
        if args is None:
            args = (1.0,)*self.numargs
        return args + self.fit_loc_scale(data, *args)

    # Return the (possibly reduced) function to optimize in order to find MLE
    #  estimates for the .fit method
    def _reduce_func(self, args, kwds):
        args = list(args)
        Nargs = len(args)
        fixedn = []
        index = list(range(Nargs))
        names = ['f%d' % n for n in range(Nargs - 2)] + ['floc', 'fscale']
        x0 = []
        for n, key in zip(index, names):
            if key in kwds:
                fixedn.append(n)
                args[n] = kwds[key]
            else:
                x0.append(args[n])
        method = kwds.get('method', 'ml').lower()
        if method.startswith('mps'):
            fitfun = self.nlogps
        else:
            fitfun = self._penalized_nnlf

        if len(fixedn) == 0:
            func = fitfun
            restore = None
        else:
            if len(fixedn) == len(index):
                raise ValueError(
                    "All parameters fixed. There is nothing to optimize.")

            def restore(args, theta):
                # Replace with theta for all numbers not in fixedn
                # This allows the non-fixed values to vary, but
                #  we still call self.nnlf with all parameters.
                i = 0
                for n in range(Nargs):
                    if n not in fixedn:
                        args[n] = theta[i]
                        i += 1
                return args

            def func(theta, x):
                newtheta = restore(args[:], theta)
                return fitfun(newtheta, x)

        return x0, func, restore, args

    def fit(self, data, *args, **kwds):
        """
        Return MLEs for shape, location, and scale parameters from data.

        MLE stands for Maximum Likelihood Estimate.  Starting estimates for
        the fit are given by input arguments; for any arguments not provided
        with starting estimates, ``self._fitstart(data)`` is called to generate
        such.

        One can hold some parameters fixed to specific values by passing in
        keyword arguments ``f0``, ``f1``, ..., ``fn`` (for shape parameters)
        and ``floc`` and ``fscale`` (for location and scale parameters,
        respectively).

        Parameters
        ----------
        data : array_like
            Data to use in calculating the MLEs.
        args : floats, optional
            Starting value(s) for any shape-characterizing arguments (those not
            provided will be determined by a call to ``_fitstart(data)``).
            No default value.
        kwds : floats, optional
            Starting values for the location and scale parameters; no default.
            Special keyword arguments are recognized as holding certain
            parameters fixed:

            f0...fn : hold respective shape parameters fixed.

            floc : hold location parameter fixed to specified value.

            fscale : hold scale parameter fixed to specified value.

            optimizer : The optimizer to use.  The optimizer must take func,
                        and starting position as the first two arguments,
                        plus args (for extra arguments to pass to the
                        function to be optimized) and disp=0 to suppress
                        output as keyword arguments.

        Returns
        -------
        shape, loc, scale : tuple of floats
            MLEs for any shape statistics, followed by those for location and
            scale.

        Notes
        -----
        This fit is computed by maximizing a log-likelihood function, with
        penalty applied for samples outside of range of the distribution. The
        returned answer is not guaranteed to be the globally optimal MLE, it
        may only be locally optimal, or the optimization may fail altogether.
        """
        Narg = len(args)
        if Narg > self.numargs:
            raise TypeError("Too many input arguments.")

        start = [None]*2
        if (Narg < self.numargs) or not ('loc' in kwds and
                                         'scale' in kwds):
            # get distribution specific starting locations
            start = self._fitstart(data)
            args += start[Narg:-2]
        loc = kwds.get('loc', start[-2])
        scale = kwds.get('scale', start[-1])
        args += (loc, scale)
        x0, func, restore, args = self._reduce_func(args, kwds)

        optimizer = kwds.get('optimizer', optimize.fmin)
        # convert string to function in scipy.optimize
        if not callable(optimizer) and isinstance(optimizer, string_types):
            if not optimizer.startswith('fmin_'):
                optimizer = "fmin_"+optimizer
            if optimizer == 'fmin_':
                optimizer = 'fmin'
            try:
                optimizer = getattr(optimize, optimizer)
            except AttributeError:
                raise ValueError("%s is not a valid optimizer" % optimizer)
        vals = optimizer(func, x0, args=(ravel(data),), disp=0)
        if restore is not None:
            vals = restore(args, vals)
        vals = tuple(vals)
        return vals

    def fit2(self, data, *args, **kwds):
        ''' Return Maximum Likelihood or Maximum Product Spacing estimator object

        Parameters
        ----------
        data : array-like
            Data to use in calculating the ML or MPS estimators
        args : optional
            Starting values for any shape arguments (those not specified
            will be determined by dist._fitstart(data))
        kwds : loc, scale
            Starting values for the location and scale parameters
            Special keyword arguments are recognized as holding certain
            parameters fixed:
                f0..fn : hold respective shape paramters fixed
                floc : hold location parameter fixed to specified value
                fscale : hold scale parameter fixed to specified value
            method : of estimation. Options are
                'ml' : Maximum Likelihood method (default)
                'mps': Maximum Product Spacing method
            alpha : scalar, optional
                Confidence coefficent  (default=0.05)
            search : bool
                If true search for best estimator (default),
                otherwise return object with initial distribution parameters
            copydata : bool
                If true copydata (default)
            optimizer : The optimizer to use.  The optimizer must take func,
                         and starting position as the first two arguments,
                         plus args (for extra arguments to pass to the
                         function to be optimized) and disp=0 to suppress
                         output as keyword arguments.

        Return
        ------
        phat : FitDistribution object
            Fitted distribution object with following member variables:
            LLmax  : loglikelihood function evaluated using par
            LPSmax : log product spacing function evaluated using par
            pvalue : p-value for the fit
            par : distribution parameters (fixed and fitted)
            par_cov : covariance of distribution parameters
            par_fix : fixed distribution parameters
            par_lower : lower (1-alpha)% confidence bound for the parameters
            par_upper : upper (1-alpha)% confidence bound for the parameters

        Note
        ----
        `data` is sorted using this function, so if `copydata`==False the data
        in your namespace will be sorted as well.
        '''
        return FitDistribution(self, data, *args, **kwds)

    def fit_loc_scale(self, data, *args):
        """
        Estimate loc and scale parameters from data using 1st and 2nd moments.

        Parameters
        ----------
        data : array_like
            Data to fit.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).

        Returns
        -------
        Lhat : float
            Estimated location parameter for the data.
        Shat : float
            Estimated scale parameter for the data.

        """
        mu, mu2 = self.stats(*args, **{'moments': 'mv'})
        tmp = asarray(data)
        muhat = tmp.mean()
        mu2hat = tmp.var()
        Shat = sqrt(mu2hat / mu2)
        Lhat = muhat - Shat*mu
        if not np.isfinite(Lhat):
            Lhat = 0
        if not (np.isfinite(Shat) and (0 < Shat)):
            Shat = 1
        return Lhat, Shat

    @np.deprecate
    def est_loc_scale(self, data, *args):
        """This function is deprecated, use self.fit_loc_scale(data) instead.
        """
        return self.fit_loc_scale(data, *args)

    def _entropy(self, *args):
        def integ(x):
            val = self._pdf(x, *args)
            return -xlogy(val, val)

        # upper limit is often inf, so suppress warnings when integrating
        olderr = np.seterr(over='ignore')
        h = integrate.quad(integ, self.a, self.b)[0]
        np.seterr(**olderr)

        if not np.isnan(h):
            return h
        else:
            # try with different limits if integration problems
            low, upp = self.ppf([1e-10, 1. - 1e-10], *args)
            if np.isinf(self.b):
                upper = upp
            else:
                upper = self.b
            if np.isinf(self.a):
                lower = low
            else:
                lower = self.a
            return integrate.quad(integ, lower, upper)[0]

    def entropy(self, *args, **kwds):
        """
        Differential entropy of the RV.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).
        scale : array_like, optional
            Scale parameter (default=1).

        """
        args, loc, scale = self._parse_args(*args, **kwds)
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (scale > 0) & (loc == loc)
        output = zeros(shape(cond0), 'd')
        place(output, (1-cond0), self.badvalue)
        goodargs = argsreduce(cond0, *args)
        # np.vectorize doesn't work when numargs == 0 in numpy 1.5.1
        if self.numargs == 0:
            place(output, cond0, self._entropy() + log(scale))
        else:
            place(output, cond0, self.vecentropy(*goodargs) + log(scale))

        return output

    def expect(self, func=None, args=(), loc=0, scale=1, lb=None, ub=None,
               conditional=False, **kwds):
        """Calculate expected value of a function with respect to the
        distribution.

        The expected value of a function ``f(x)`` with respect to a
        distribution ``dist`` is defined as::

                    ubound
            E[x] = Integral(f(x) * dist.pdf(x))
                    lbound

        Parameters
        ----------
        func : callable, optional
            Function for which integral is calculated. Takes only one argument.
            The default is the identity mapping f(x) = x.
        args : tuple, optional
            Argument (parameters) of the distribution.
        lb, ub : scalar, optional
            Lower and upper bound for integration. default is set to the
            support of the distribution.
        conditional : bool, optional
            If True, the integral is corrected by the conditional probability
            of the integration interval.  The return value is the expectation
            of the function, conditional on being in the given interval.
            Default is False.

        Additional keyword arguments are passed to the integration routine.

        Returns
        -------
        expect : float
            The calculated expected value.

        Notes
        -----
        The integration behavior of this function is inherited from
        `integrate.quad`.

        """
        lockwds = {'loc': loc,
                   'scale': scale}
        self._argcheck(*args)
        if func is None:
            def fun(x, *args):
                return x * self.pdf(x, *args, **lockwds)
        else:
            def fun(x, *args):
                return func(x) * self.pdf(x, *args, **lockwds)
        if lb is None:
            lb = loc + self.a * scale
        if ub is None:
            ub = loc + self.b * scale
        if conditional:
            invfac = (self.sf(lb, *args, **lockwds)
                      - self.sf(ub, *args, **lockwds))
        else:
            invfac = 1.0
        kwds['args'] = args
        # Silence floating point warnings from integration.
        olderr = np.seterr(all='ignore')
        vals = integrate.quad(fun, lb, ub, **kwds)[0] / invfac
        np.seterr(**olderr)
        return vals


## Handlers for generic case where xk and pk are given
## The _drv prefix probably means discrete random variable.

def _drv_pmf(self, xk, *args):
    try:
        return self.P[xk]
    except KeyError:
        return 0.0


def _drv_cdf(self, xk, *args):
    indx = argmax((self.xk > xk), axis=-1)-1
    return self.F[self.xk[indx]]


def _drv_ppf(self, q, *args):
    indx = argmax((self.qvals >= q), axis=-1)
    return self.Finv[self.qvals[indx]]


def _drv_nonzero(self, k, *args):
    return 1


def _drv_moment(self, n, *args):
    n = asarray(n)
    return sum(self.xk**n[np.newaxis, ...] * self.pk, axis=0)


def _drv_moment_gen(self, t, *args):
    t = asarray(t)
    return sum(exp(self.xk * t[np.newaxis, ...]) * self.pk, axis=0)


def _drv2_moment(self, n, *args):
    """Non-central moment of discrete distribution."""
    # many changes, originally not even a return
    tot = 0.0
    diff = 1e100
    # pos = self.a
    pos = max(0.0, 1.0*self.a)
    count = 0
    # handle cases with infinite support
    ulimit = max(1000, (min(self.b, 1000) + max(self.a, -1000))/2.0)
    llimit = min(-1000, (min(self.b, 1000) + max(self.a, -1000))/2.0)

    while (pos <= self.b) and ((pos <= ulimit) or
                               (diff > self.moment_tol)):
        diff = np.power(pos, n) * self.pmf(pos, *args)
        # use pmf because _pmf does not check support in randint and there
        # might be problems ? with correct self.a, self.b at this stage
        tot += diff
        pos += self.inc
        count += 1

    if self.a < 0:  # handle case when self.a = -inf
        diff = 1e100
        pos = -self.inc
        while (pos >= self.a) and ((pos >= llimit) or
                                   (diff > self.moment_tol)):
            diff = np.power(pos, n) * self.pmf(pos, *args)
            # using pmf instead of _pmf, see above
            tot += diff
            pos -= self.inc
            count += 1
    return tot


def _drv2_ppfsingle(self, q, *args):  # Use basic bisection algorithm
    b = self.b
    a = self.a
    if isinf(b):            # Be sure ending point is > q
        b = int(max(100*q, 10))
        while 1:
            if b >= self.b:
                qb = 1.0
                break
            qb = self._cdf(b, *args)
            if (qb < q):
                b += 10
            else:
                break
    else:
        qb = 1.0
    if isinf(a):    # be sure starting point < q
        a = int(min(-100*q, -10))
        while 1:
            if a <= self.a:
                qb = 0.0
                break
            qa = self._cdf(a, *args)
            if (qa > q):
                a -= 10
            else:
                break
    else:
        qa = self._cdf(a, *args)

    while 1:
        if (qa == q):
            return a
        if (qb == q):
            return b
        if b <= a+1:
            # testcase: return wrong number at lower index
            # python -c "from scipy.stats import zipf;print zipf.ppf(0.01, 2)" wrong
            # python -c "from scipy.stats import zipf;print zipf.ppf([0.01, 0.61, 0.77, 0.83], 2)"
            # python -c "from scipy.stats import logser;print logser.ppf([0.1, 0.66, 0.86, 0.93], 0.6)"
            if qa > q:
                return a
            else:
                return b
        c = int((a+b)/2.0)
        qc = self._cdf(c, *args)
        if (qc < q):
            if a != c:
                a = c
            else:
                raise RuntimeError('updating stopped, endless loop')
            qa = qc
        elif (qc > q):
            if b != c:
                b = c
            else:
                raise RuntimeError('updating stopped, endless loop')
            qb = qc
        else:
            return c


def entropy(pk, qk=None, base=None):
    """Calculate the entropy of a distribution for given probability values.

    If only probabilities `pk` are given, the entropy is calculated as
    ``S = -sum(pk * log(pk), axis=0)``.

    If `qk` is not None, then compute the Kullback-Leibler divergence
    ``S = sum(pk * log(pk / qk), axis=0)``.

    This routine will normalize `pk` and `qk` if they don't sum to 1.

    Parameters
    ----------
    pk : sequence
        Defines the (discrete) distribution. ``pk[i]`` is the (possibly
        unnormalized) probability of event ``i``.
    qk : sequence, optional
        Sequence against which the relative entropy is computed. Should be in
        the same format as `pk`.
    base : float, optional
        The logarithmic base to use, defaults to ``e`` (natural logarithm).

    Returns
    -------
    S : float
        The calculated entropy.

    """
    pk = asarray(pk)
    pk = 1.0*pk / sum(pk, axis=0)
    if qk is None:
        vec = xlogy(pk, pk)
    else:
        qk = asarray(qk)
        if len(qk) != len(pk):
            raise ValueError("qk and pk must have same length.")
        qk = 1.0*qk / sum(qk, axis=0)
        # If qk is zero anywhere, then unless pk is zero at those places
        #   too, the relative entropy is infinite.
        mask = qk == 0.0
        qk[mask] = 1.0  # Avoid the divide-by-zero warning
        quotient = pk / qk
        vec = -xlogy(pk, quotient)
        vec[mask & (pk != 0.0)] = -inf
        vec[mask & (pk == 0.0)] = 0.0
    S = -sum(vec, axis=0)
    if base is not None:
        S /= log(base)
    return S


# Must over-ride one of _pmf or _cdf or pass in
#  x_k, p(x_k) lists in initialization

class rv_discrete(rv_generic):
    """
    A generic discrete random variable class meant for subclassing.

    `rv_discrete` is a base class to construct specific distribution classes
    and instances from for discrete random variables. rv_discrete can be used
    to construct an arbitrary distribution with defined by a list of support
    points and the corresponding probabilities.

    Parameters
    ----------
    a : float, optional
        Lower bound of the support of the distribution, default: 0
    b : float, optional
        Upper bound of the support of the distribution, default: plus infinity
    moment_tol : float, optional
        The tolerance for the generic calculation of moments
    values : tuple of two array_like
        (xk, pk) where xk are points (integers) with positive probability pk
        with sum(pk) = 1
    inc : integer
        increment for the support of the distribution, default: 1
        other values have not been tested
    badvalue : object, optional
        The value in (masked) arrays that indicates a value that should be
        ignored.
    name : str, optional
        The name of the instance. This string is used to construct the default
        example for distributions.
    longname : str, optional
        This string is used as part of the first line of the docstring returned
        when a subclass has no docstring of its own. Note: `longname` exists
        for backwards compatibility, do not use for new subclasses.
    shapes : str, optional
        The shape of the distribution. For example ``"m, n"`` for a
        distribution that takes two integers as the first two arguments for all
        its methods.
    extradoc :  str, optional
        This string is used as the last part of the docstring returned when a
        subclass has no docstring of its own. Note: `extradoc` exists for
        backwards compatibility, do not use for new subclasses.

    Methods
    -------
    ``generic.rvs(<shape(s)>, loc=0, size=1)``
        random variates

    ``generic.pmf(x, <shape(s)>, loc=0)``
        probability mass function

    ``logpmf(x, <shape(s)>, loc=0)``
        log of the probability density function

    ``generic.cdf(x, <shape(s)>, loc=0)``
        cumulative density function

    ``generic.logcdf(x, <shape(s)>, loc=0)``
        log of the cumulative density function

    ``generic.sf(x, <shape(s)>, loc=0)``
        survival function (1-cdf --- sometimes more accurate)

    ``generic.logsf(x, <shape(s)>, loc=0, scale=1)``
        log of the survival function

    ``generic.ppf(q, <shape(s)>, loc=0)``
        percent point function (inverse of cdf --- percentiles)

    ``generic.isf(q, <shape(s)>, loc=0)``
        inverse survival function (inverse of sf)

    ``generic.moment(n, <shape(s)>, loc=0)``
        non-central n-th moment of the distribution.  May not work for array
        arguments.

    ``generic.stats(<shape(s)>, loc=0, moments='mv')``
        mean('m', axis=0), variance('v'), skew('s'), and/or kurtosis('k')

    ``generic.entropy(<shape(s)>, loc=0)``
        entropy of the RV

    ``generic.expect(func=None, args=(), loc=0, lb=None, ub=None, conditional=False)``
        Expected value of a function with respect to the distribution.
        Additional kwd arguments passed to integrate.quad

    ``generic.median(<shape(s)>, loc=0)``
        Median of the distribution.

    ``generic.mean(<shape(s)>, loc=0)``
        Mean of the distribution.

    ``generic.std(<shape(s)>, loc=0)``
        Standard deviation of the distribution.

    ``generic.var(<shape(s)>, loc=0)``
        Variance of the distribution.

    ``generic.interval(alpha, <shape(s)>, loc=0)``
        Interval that with `alpha` percent probability contains a random
        realization of this distribution.

    ``generic(<shape(s)>, loc=0)``
        calling a distribution instance returns a frozen distribution

    Notes
    -----

    You can construct an arbitrary discrete rv where ``P{X=xk} = pk``
    by passing to the rv_discrete initialization method (through the
    values=keyword) a tuple of sequences (xk, pk) which describes only those
    values of X (xk) that occur with nonzero probability (pk).

    To create a new discrete distribution, we would do the following::

        class poisson_gen(rv_discrete):
            # "Poisson distribution"
            def _pmf(self, k, mu):
                ...

    and create an instance::

        poisson = poisson_gen(name="poisson",
                              longname='A Poisson')

    The docstring can be created from a template.

    Alternatively, the object may be called (as a function) to fix the shape
    and location parameters returning a "frozen" discrete RV object::

        myrv = generic(<shape(s)>, loc=0)
            - frozen RV object with the same methods but holding the given
              shape and location fixed.

    A note on ``shapes``: subclasses need not specify them explicitly. In this
    case, the `shapes` will be automatically deduced from the signatures of the
    overridden methods.
    If, for some reason, you prefer to avoid relying on introspection, you can
    specify ``shapes`` explicitly as an argument to the instance constructor.


    Examples
    --------

    Custom made discrete distribution:

    >>> from scipy import stats
    >>> xk = np.arange(7)
    >>> pk = (0.1, 0.2, 0.3, 0.1, 0.1, 0.0, 0.2)
    >>> custm = stats.rv_discrete(name='custm', values=(xk, pk))
    >>>
    >>> import matplotlib.pyplot as plt
    >>> fig, ax = plt.subplots(1, 1)
    >>> ax.plot(xk, custm.pmf(xk), 'ro', ms=12, mec='r')
    >>> ax.vlines(xk, 0, custm.pmf(xk), colors='r', lw=4)
    >>> plt.show()

    Random number generation:

    >>> R = custm.rvs(size=100)

    Check accuracy of cdf and ppf:

    >>> prb = custm.cdf(x, <shape(s)>)
    >>> h = plt.semilogy(np.abs(x-custm.ppf(prb, <shape(s)>))+1e-20)
    """

    def __init__(self, a=0, b=inf, name=None, badvalue=None,
                 moment_tol=1e-8, values=None, inc=1, longname=None,
                 shapes=None, extradoc=None):

        super(rv_discrete, self).__init__()

        # cf generic freeze
        self._ctor_param = dict(
            a=a, b=b, name=name, badvalue=badvalue,
            moment_tol=moment_tol, values=values, inc=inc,
            longname=longname, shapes=shapes, extradoc=extradoc)

        if badvalue is None:
            badvalue = nan
        if name is None:
            name = 'Distribution'
        self.badvalue = badvalue
        self.a = a
        self.b = b
        self.name = name
        self.moment_tol = moment_tol
        self.inc = inc
        self._cdfvec = vectorize(self._cdf_single, otypes='d')
        self.return_integers = 1
        self.vecentropy = vectorize(self._entropy)
        self.shapes = shapes
        self.extradoc = extradoc

        if values is not None:
            self.xk, self.pk = values
            self.return_integers = 0
            indx = argsort(ravel(self.xk))
            self.xk = take(ravel(self.xk), indx, 0)
            self.pk = take(ravel(self.pk), indx, 0)
            self.a = self.xk[0]
            self.b = self.xk[-1]
            self.P = dict(zip(self.xk, self.pk))
            self.qvals = np.cumsum(self.pk, axis=0)
            self.F = dict(zip(self.xk, self.qvals))
            decreasing_keys = sorted(self.F.keys(), reverse=True)
            self.Finv = dict((self.F[k], k) for k in decreasing_keys)
            self._ppf = instancemethod(vectorize(_drv_ppf, otypes='d'),
                                       self, rv_discrete)
            self._pmf = instancemethod(vectorize(_drv_pmf, otypes='d'),
                                       self, rv_discrete)
            self._cdf = instancemethod(vectorize(_drv_cdf, otypes='d'),
                                       self, rv_discrete)
            self._nonzero = instancemethod(_drv_nonzero, self, rv_discrete)
            self.generic_moment = instancemethod(_drv_moment,
                                                 self, rv_discrete)
            self.moment_gen = instancemethod(_drv_moment_gen,
                                             self, rv_discrete)
            self._construct_argparser(meths_to_inspect=[_drv_pmf],
                                      locscale_in='loc=0',
                                      # scale=1 for discrete RVs
                                      locscale_out='loc, 1')
        else:
            self._construct_argparser(meths_to_inspect=[self._pmf, self._cdf],
                                      locscale_in='loc=0',
                                      # scale=1 for discrete RVs
                                      locscale_out='loc, 1')

            # nin correction needs to be after we know numargs
            # correct nin for generic moment vectorization
            _vec_generic_moment = vectorize(_drv2_moment, otypes='d')
            _vec_generic_moment.nin = self.numargs + 2
            self.generic_moment = instancemethod(_vec_generic_moment,
                                                 self, rv_discrete)
            # backwards compat.  was removed in 0.14.0, put back but
            # deprecated in 0.14.1:
            self.vec_generic_moment = np.deprecate(_vec_generic_moment,
                                                   "vec_generic_moment",
                                                   "generic_moment")

            # correct nin for ppf vectorization
            _vppf = vectorize(_drv2_ppfsingle, otypes='d')
            _vppf.nin = self.numargs + 2  # +1 is for self
            self._ppfvec = instancemethod(_vppf,
                                          self, rv_discrete)

        # now that self.numargs is defined, we can adjust nin
        self._cdfvec.nin = self.numargs + 1

        # generate docstring for subclass instances
        if longname is None:
            if name[0] in ['aeiouAEIOU']:
                hstr = "An "
            else:
                hstr = "A "
            longname = hstr + name

        if sys.flags.optimize < 2:
            # Skip adding docstrings if interpreter is run with -OO
            if self.__doc__ is None:
                self._construct_default_doc(longname=longname,
                                            extradoc=extradoc)
            else:
                dct = dict(distdiscrete)
                self._construct_doc(docdict_discrete, dct.get(self.name))

            #discrete RV do not have the scale parameter, remove it
            self.__doc__ = self.__doc__.replace(
                '\n    scale : array_like, '
                'optional\n        scale parameter (default=1)', '')

    def _construct_default_doc(self, longname=None, extradoc=None):
        """Construct instance docstring from the rv_discrete template."""
        if extradoc is None:
            extradoc = ''
        if extradoc.startswith('\n\n'):
            extradoc = extradoc[2:]
        self.__doc__ = ''.join(['%s discrete random variable.' % longname,
                                '\n\n%(before_notes)s\n', docheaders['notes'],
                                extradoc, '\n%(example)s'])
        self._construct_doc(docdict_discrete)

    def _nonzero(self, k, *args):
        return floor(k) == k

    def _pmf(self, k, *args):
        return self._cdf(k, *args) - self._cdf(k-1, *args)

    def _logpmf(self, k, *args):
        return log(self._pmf(k, *args))

    def _cdf_single(self, k, *args):
        m = arange(int(self.a), k+1)
        return sum(self._pmf(m, *args), axis=0)

    def _cdf(self, x, *args):
        k = floor(x)
        return self._cdfvec(k, *args)

    # generic _logcdf, _sf, _logsf, _ppf, _isf, _rvs defined in rv_generic

    def rvs(self, *args, **kwargs):
        """
        Random variates of given type.

        Parameters
        ----------
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).
        size : int or tuple of ints, optional
            Defining number of random variates (default=1).  Note that `size`
            has to be given as keyword, not as positional argument.

        Returns
        -------
        rvs : ndarray or scalar
            Random variates of given `size`.

        """
        kwargs['discrete'] = True
        return super(rv_discrete, self).rvs(*args, **kwargs)

    def pmf(self, k, *args, **kwds):
        """
        Probability mass function at k of the given RV.

        Parameters
        ----------
        k : array_like
            quantiles
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information)
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        pmf : array_like
            Probability mass function evaluated at k

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray((k-loc))
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k <= self.b) & self._nonzero(k, *args)
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, np.clip(self._pmf(*goodargs), 0, 1))
        if output.ndim == 0:
            return output[()]
        return output

    def logpmf(self, k, *args, **kwds):
        """
        Log of the probability mass function at k of the given RV.

        Parameters
        ----------
        k : array_like
            Quantiles.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter. Default is 0.

        Returns
        -------
        logpmf : array_like
            Log of the probability mass function evaluated at k.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray((k-loc))
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k <= self.b) & self._nonzero(k, *args)
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, self._logpmf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def cdf(self, k, *args, **kwds):
        """
        Cumulative distribution function of the given RV.

        Parameters
        ----------
        k : array_like, int
            Quantiles.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        cdf : ndarray
            Cumulative distribution function evaluated at `k`.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray((k-loc))
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k < self.b)
        cond2 = (k >= self.b)
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        place(output, cond2*(cond0 == cond0), 1.0)

        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, np.clip(self._cdf(*goodargs), 0, 1))
        if output.ndim == 0:
            return output[()]
        return output

    def logcdf(self, k, *args, **kwds):
        """
        Log of the cumulative distribution function at k of the given RV

        Parameters
        ----------
        k : array_like, int
            Quantiles.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        logcdf : array_like
            Log of the cumulative distribution function evaluated at k.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray((k-loc))
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k < self.b)
        cond2 = (k >= self.b)
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        place(output, cond2*(cond0 == cond0), 0.0)

        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, self._logcdf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def sf(self, k, *args, **kwds):
        """
        Survival function (1-cdf) at k of the given RV.

        Parameters
        ----------
        k : array_like
            Quantiles.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        sf : array_like
            Survival function evaluated at k.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray(k-loc)
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k <= self.b)
        cond2 = (k < self.a) & cond0
        cond = cond0 & cond1
        output = zeros(shape(cond), 'd')
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        place(output, cond2, 1.0)
        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, np.clip(self._sf(*goodargs), 0, 1))
        if output.ndim == 0:
            return output[()]
        return output

    def logsf(self, k, *args, **kwds):
        """
        Log of the survival function of the given RV.

        Returns the log of the "survival function," defined as ``1 - cdf``,
        evaluated at `k`.

        Parameters
        ----------
        k : array_like
            Quantiles.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        logsf : ndarray
            Log of the survival function evaluated at `k`.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        k, loc = map(asarray, (k, loc))
        args = tuple(map(asarray, args))
        k = asarray(k-loc)
        cond0 = self._argcheck(*args)
        cond1 = (k >= self.a) & (k <= self.b)
        cond2 = (k < self.a) & cond0
        cond = cond0 & cond1
        output = empty(shape(cond), 'd')
        output.fill(NINF)
        place(output, (1-cond0) + np.isnan(k), self.badvalue)
        place(output, cond2, 0.0)
        if any(cond):
            goodargs = argsreduce(cond, *((k,)+args))
            place(output, cond, self._logsf(*goodargs))
        if output.ndim == 0:
            return output[()]
        return output

    def ppf(self, q, *args, **kwds):
        """
        Percent point function (inverse of cdf) at q of the given RV

        Parameters
        ----------
        q : array_like
            Lower tail probability.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).
        scale : array_like, optional
            Scale parameter (default=1).

        Returns
        -------
        k : array_like
            Quantile corresponding to the lower tail probability, q.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        q, loc = map(asarray, (q, loc))
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (loc == loc)
        cond1 = (q > 0) & (q < 1)
        cond2 = (q == 1) & cond0
        cond = cond0 & cond1
        output = valarray(shape(cond), value=self.badvalue, typecode='d')
        # output type 'd' to handle nin and inf
        place(output, (q == 0)*(cond == cond), self.a-1)
        place(output, cond2, self.b)
        if any(cond):
            goodargs = argsreduce(cond, *((q,)+args+(loc,)))
            loc, goodargs = goodargs[-1], goodargs[:-1]
            place(output, cond, self._ppf(*goodargs) + loc)

        if output.ndim == 0:
            return output[()]
        return output

    def isf(self, q, *args, **kwds):
        """
        Inverse survival function (inverse of `sf`) at q of the given RV.

        Parameters
        ----------
        q : array_like
            Upper tail probability.
        arg1, arg2, arg3,... : array_like
            The shape parameter(s) for the distribution (see docstring of the
            instance object for more information).
        loc : array_like, optional
            Location parameter (default=0).

        Returns
        -------
        k : ndarray or scalar
            Quantile corresponding to the upper tail probability, q.

        """
        args, loc, _ = self._parse_args(*args, **kwds)
        q, loc = map(asarray, (q, loc))
        args = tuple(map(asarray, args))
        cond0 = self._argcheck(*args) & (loc == loc)
        cond1 = (q > 0) & (q < 1)
        cond2 = (q == 1) & cond0
        cond = cond0 & cond1

        # same problem as with ppf; copied from ppf and changed
        output = valarray(shape(cond), value=self.badvalue, typecode='d')
        # output type 'd' to handle nin and inf
        place(output, (q == 0)*(cond == cond), self.b)
        place(output, cond2, self.a-1)

        # call place only if at least 1 valid argument
        if any(cond):
            goodargs = argsreduce(cond, *((q,)+args+(loc,)))
            loc, goodargs = goodargs[-1], goodargs[:-1]
            # PB same as ticket 766
            place(output, cond, self._isf(*goodargs) + loc)

        if output.ndim == 0:
            return output[()]
        return output

    def _entropy(self, *args):
        if hasattr(self, 'pk'):
            return entropy(self.pk)
        else:
            mu = int(self.stats(*args, **{'moments': 'm'}))
            val = self.pmf(mu, *args)
            ent = -xlogy(val, val)
            k = 1
            term = 1.0
            while (abs(term) > _EPS):
                val = self.pmf(mu+k, *args)
                term = -xlogy(val, val)
                val = self.pmf(mu-k, *args)
                term -= xlogy(val, val)
                k += 1
                ent += term
            return ent

    def expect(self, func=None, args=(), loc=0, lb=None, ub=None,
               conditional=False):
        """
        Calculate expected value of a function with respect to the distribution
        for discrete distribution

        Parameters
        ----------
        fn : function (default: identity mapping)
            Function for which sum is calculated. Takes only one argument.
        args : tuple
            argument (parameters) of the distribution
        lb, ub : numbers, optional
            lower and upper bound for integration, default is set to the
            support of the distribution, lb and ub are inclusive (ul<=k<=ub)
        conditional : bool, optional
            Default is False.
            If true then the expectation is corrected by the conditional
            probability of the integration interval. The return value is the
            expectation of the function, conditional on being in the given
            interval (k such that ul<=k<=ub).

        Returns
        -------
        expect : float
            Expected value.

        Notes
        -----
        * function is not vectorized
        * accuracy: uses self.moment_tol as stopping criterium
          for heavy tailed distribution e.g. zipf(4), accuracy for
          mean, variance in example is only 1e-5,
          increasing precision (moment_tol) makes zipf very slow
        * suppnmin=100 internal parameter for minimum number of points to
          evaluate could be added as keyword parameter, to evaluate functions
          with non-monotonic shapes, points include integers in (-suppnmin,
          suppnmin)
        * uses maxcount=1000 limits the number of points that are evaluated
          to break loop for infinite sums
          (a maximum of suppnmin+1000 positive plus suppnmin+1000 negative
          integers are evaluated)

        """

        # moment_tol = 1e-12 # increase compared to self.moment_tol,
        # too slow for only small gain in precision for zipf

        # avoid endless loop with unbound integral, eg. var of zipf(2)
        maxcount = 1000
        suppnmin = 100  # minimum number of points to evaluate (+ and -)

        if func is None:
            def fun(x):
                # loc and args from outer scope
                return (x+loc)*self._pmf(x, *args)
        else:
            def fun(x):
                # loc and args from outer scope
                return func(x+loc)*self._pmf(x, *args)
        # used pmf because _pmf does not check support in randint and there
        # might be problems(?) with correct self.a, self.b at this stage maybe
        # not anymore, seems to work now with _pmf

        self._argcheck(*args)  # (re)generate scalar self.a and self.b
        if lb is None:
            lb = (self.a)
        else:
            lb = lb - loc   # convert bound for standardized distribution
        if ub is None:
            ub = (self.b)
        else:
            ub = ub - loc   # convert bound for standardized distribution
        if conditional:
            if np.isposinf(ub)[()]:
                # work around bug: stats.poisson.sf(stats.poisson.b, 2) is nan
                invfac = 1 - self.cdf(lb-1, *args)
            else:
                invfac = 1 - self.cdf(lb-1, *args) - self.sf(ub, *args)
        else:
            invfac = 1.0

        #tot = 0.0
        low, upp = self._ppf(0.001, *args), self._ppf(0.999, *args)
        low = max(min(-suppnmin, low), lb)
        upp = min(max(suppnmin, upp), ub)
        supp = np.arange(low, upp+1, self.inc)  # check limits
        tot = np.sum(fun(supp))
        diff = 1e100
        pos = upp + self.inc
        count = 0

        # handle cases with infinite support

        while (pos <= ub) and (diff > self.moment_tol) and count <= maxcount:
            diff = fun(pos)
            tot += diff
            pos += self.inc
            count += 1

        if self.a < 0:  # handle case when self.a = -inf
            diff = 1e100
            pos = low - self.inc
            while ((pos >= lb) and (diff > self.moment_tol) and
                   count <= maxcount):
                diff = fun(pos)
                tot += diff
                pos -= self.inc
                count += 1
        if count > maxcount:
            warnings.warn('expect(): sum did not converge', RuntimeWarning)
        return tot/invfac


def get_distribution_names(namespace_pairs, rv_base_class):
    """
    Collect names of statistical distributions and their generators.

    Parameters
    ----------
    namespace_pairs : sequence
        A snapshot of (name, value) pairs in the namespace of a module.
    rv_base_class : class
        The base class of random variable generator classes in a module.

    Returns
    -------
    distn_names : list of strings
        Names of the statistical distributions.
    distn_gen_names : list of strings
        Names of the generators of the statistical distributions.
        Note that these are not simply the names of the statistical
        distributions, with a _gen suffix added.

    """
    distn_names = []
    distn_gen_names = []
    for name, value in namespace_pairs:
        if name.startswith('_'):
            continue
        if name.endswith('_gen') and issubclass(value, rv_base_class):
            distn_gen_names.append(name)
        if isinstance(value, rv_base_class):
            distn_names.append(name)
    return distn_names, distn_gen_names
