"""

"""
import numpy as np
from scipy.spatial.distance import pdist
from scipy.ndimage.interpolation import zoom
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from skgstat import binning, estimators


class SpaceTimeVariogram:
    """

    """
    def __init__(self,
                 coordinates,
                 values,
                 xdist_func='euclidean',
                 tdist_func='euclidean',
                 x_lags=10,
                 t_lags='max',
                 maxlag=None,
                 xbins='even',
                 tbins='even',
                 estimator='matheron',

                 verbose=False
                 ):
        # set coordinates array
        self._X = np.asarray(coordinates)

        # combined pairwise differences
        self._diff = None

        # set verbosity, not implemented yet
        self.verbose = verbose

        # set attributes to be fulled during calculation
        self.cov = None
        self.cof = None

        # set values
        self._values = None
        self.set_values(values=values)

        # distance matrix for space and time
        self._xdist = None
        self._tdist = None

        # set distance caluclation functions
        self._xdist_func = None
        self._tdist_func = None
        self.set_xdist_func(func_name=xdist_func)
        self.set_tdist_func(func_name=tdist_func)

        # lags and max lag
        self._x_lags = None
        self.x_lags = x_lags
        self._t_lags = None
        self.t_lags = t_lags
        self._maxlag = None
        self.maxlag = maxlag

        # estimator settings
        self._estimator = None
        self.set_estimator(estimator_name=estimator)

        # initialize binning arrays
        # space
        self._xbin_func = None
        self._xgroups = None
        self._xbins = None
        self.set_bin_func(bin_func=xbins, axis='space')

        # time
        self._tbin_func = None
        self._tgroups = None
        self._tbins = None
        self.set_bin_func(bin_func=tbins, axis='time')

        # do one preprocessing run
        self.preprocessing(force=True)

    # ------------------------------------------------------------------------ #
    #                        ATTRIBUTE SETTING                                 #
    # ------------------------------------------------------------------------ #
    @property
    def values(self):
        """Values

        The SpaceTimeVariogram stores (and needs) the observations as a two
        dimensional array. The first axis (rows) need to match the coordinate
        array, but instead of containing one value for each location,
        the values shall contain a time series per location.

        Returns
        -------
        values : numpy.array
            Returns a two dimensional array of all observations. The first
            dimension (rows) matches the coordinate array and the second axis
            contains the time series for each observation point.

        """
        return self._values

    def set_values(self, values):
        """Set new values

        The values should be an (m, n) array with m matching the size of
        coordinates first  dimension and n is the time dimension.

        Raises
        ------
        ValueError : in case n <= 1 or values are not an array of correct
            dimensionality
        AttributeError : in case values cannot be converted to a numpy.array

        """
        values = np.asarray(values)

        # check dtype
        if not isinstance(values, np.ndarray) or \
                (values.dtype is not np.dtype(float) and
                 values.dtype is not np.dtype(int)):
            raise AttributeError('values cannot be converted to a proper '
                                 '(m,n) shaped array.')
        # check shape
        try:
            m, n = values.shape
            if m != self._X.shape[0]:
                raise ValueError
        except ValueError:
            raise ValueError('The values shape do not match coordinates.')

        if n <= 1:
            raise ValueError('A SpaceTimeVariogram needs more than one '
                             'observation on the time axis.')

        # save new values
        self._values = values

        # dismiss the pairwise differences, and lags
        self._diff = None

    @values.setter
    def values(self, new_values):
        self.set_values(values=new_values)

    @property
    def xdist_func(self):
        return self._xdist_func

    @xdist_func.setter
    def xdist_func(self, func):
        self.set_xdist_func(func_name=func)

    def set_xdist_func(self, func_name):
        """Set new space distance function

        Set a new function for calculating the distance matrix in the space
        dimension. At the moment only strings are supported. Will be passed
        to scipy.spatical.distance.pdist as 'metric' attribute.

        Parameters
        ----------
        func_name : str
            The name of the function used to calculate the pairwise distances.
            Will be passed to scipy.spatial.distance.pdist as the 'metric'
            attribute.

        Raises
        ------
        ValueError : in case a non-string argument is passed.

        """
        if isinstance(func_name, str):
            self._xdist_func = lambda x: pdist(x, metric=func_name)
        else:
            raise ValueError('For now only str arguments are supported.')

        # reset the distances
        self._xdist = None

    @property
    def tdist_func(self):
        return self._tdist_func

    @tdist_func.setter
    def tdist_func(self, func):
        self.set_tdist_func(func_name=func)

    def set_tdist_func(self, func_name):
        """Set new space distance function

        Set a new function for calculating the distance matrix in the space
        dimension. At the moment only strings are supported. Will be passed
        to scipy.spatical.distance.pdist as 'metric' attribute.

        Parameters
        ----------
        func_name : str
            The name of the function used to calculate the pairwise distances.
            Will be passed to scipy.spatial.distance.pdist as the 'metric'
            attribute.

        Raises
        ------
        ValueError : in case a non-string argument is passed.

        """
        if isinstance(func_name, str):
            self._tdist_func = lambda t: pdist(t, metric=func_name)
        else:
            raise ValueError('For now only str arguments are supported.')

        # reset the distances
        self._tdist = None

    @property
    def distance(self):
        """Distance matrices

        Returns both the space and time distance matrix. This property is
        equivalent to two separate calls of
        :func:`xdistance <skgstat.SpaceTimeVariogram.xdistance>` and
        :func:`tdistance <skgstat.SpaceTimeVariogram.tdistance>`.

        Returns
        -------
        distance matrices : (numpy.array, numpy.array)
            Returns a tuple of the two distance matrices in space and time.
            Each distance matrix is a flattened upper triangle of the
            distance matrix squareform in row orientation.

        """
        return self.xdistance, self.tdistance

    @property
    def xdistance(self):
        """Distance matrix (space)

        Return the upper triangle of the squareform pairwise distance matrix.

        Returns
        -------
        xdistance : numpy.array
            1D-array of the upper triangle of a squareform representation of
            the distance matrix.

        """
        self.__calc_xdist(force=False)
        return self._xdist

    @property
    def tdistance(self):
        """Time distance

        Returns a distance matrix containing the distance of all observation
        points in time. The time 'coordiantes' are created from the values
        multidimensional array, where the second dimension is assumed to be
        time. The unit will be time steps.

        Returns
        -------
        tdistance : numpy.array
            1D-array of the upper triangle of a squareform representation of
            the distance matrix.

        """
        self.__calc_tdist(force=False)
        return self._tdist

    @property
    def x_lags(self):
        return self._x_lags

    @x_lags.setter
    def x_lags(self, lags):
        if not isinstance(lags, int):
            raise ValueError('Only integers are supported as lag counts.')

        # set new value
        self._x_lags = lags

        # reset bins and groups
        self._xbins = None
        self._xgroups = None


    @property
    def t_lags(self):
        if isinstance(self._t_lags, str):
            if self._t_lags.lower() == 'max':
                return self.values.shape[1] - 1
            else:
                raise ValueError("Only 'max' supported as string argument.")
        else:
            return self._t_lags

    @t_lags.setter
    def t_lags(self, lags):
        # set new value
        self._t_lags = lags

        # reset bins
        self._tbins = None
        self._tgroups = None

    @property
    def maxlag(self):
        return self._maxlag

    @maxlag.setter
    def maxlag(self, value):
        # reset fitting
        self.cov, self.cof = None, None

        # remove binning
        self._xbins = None
        self._xgroups = None

        # set the new value
        if value is None:
            self._maxlag = None
        elif isinstance(value, str):
            if value == 'median':
                self._maxlag = np.median(self.xdistance)
            elif value == 'mean':
                self._maxlag = np.mean(self.xdistance)
        elif value < 1:
            self._maxlag = value * np.max(self.xdistance)
        else:
            self._maxlag = value

    def set_bin_func(self, bin_func, axis):
        """Set binning function

        Set a new binning function to either the space or time axis. Both axes
        support the methods: ['even', 'uniform']:

        * **'even'**, create even width bins
        * **'uniform'**, create bins of uniform distribution


        Parameters
        ----------
        bin_func : str
            Sepcifies the function to be loaded. Can be either 'even' or
            'uniform'.
        axis : str
            Specifies the axis to be used for binning. Can be either 'space' or
            'time', or one of the two shortcuts 's' and 't'

        See Also
        --------
        skgstat.binning.even_width_lags
        skgstat.binning.uniform_count_lags

        """
        # switch the function
        if bin_func.lower() == 'even':
            f = binning.even_width_lags
        elif bin_func.lower == 'uniform':
            f = binning.uniform_count_lags
        else:
            raise ValueError('%s binning method is not known' % bin_func)

        # switch the axis
        if axis.lower() == 'space' or axis.lower() == 's':
            self._xbin_func = f

            # reset
            self._xgroups = None
            self._xbins = None
        elif axis.lower() == 'time' or axis.lower() == 't':
            self._tbin_func = f

            # reset
            self._tgroups = None
            self._tbins = None
        else:
            raise ValueError('%s is not a valid axis' % axis)

        # reset fitting params
        self.cof, self.cof = None, None

    @property
    def xbins(self):
        """Spatial binning

        Returns the bin edges over the spatial axis. These can be used to
        align the spatial lag class grouping to actual distance lags. The
        length of the array matches the number of spatial lag classes.

        Returns
        -------
        bins : numpy.array
            Returns the edges of the current spatial binning.

        """
        # check if cached
        if self._xbins is None:
            self._xbins = self._xbin_func(self.xdistance,
                                          self.x_lags, self.maxlag)
        return self._xbins

    @xbins.setter
    def xbins(self, bins):
        if isinstance(bins, int):
            self._xbins = None
            self._x_lags = bins
        elif isinstance(bins, (list, tuple, np.ndarray)):
            self._xbins = np.asarray(bins)
            self._x_lags = len(self._xbins)
        elif isinstance(bins, str):
            self.set_bin_func(bin_func=bins, axis='space')
        else:
            raise AttributeError('bin value cannot be parsed.')

        # reset the groups
        self._xgroups = None

    @property
    def tbins(self):
        """Temporal binning

        Returns the bin edges over the temporal axis. These can be used to
        align the temporal lag class grouping to actual time lags. The length of
        the array matches the number of temporal lag classes.

        Returns
        -------
        bins : numpy.array
            Returns the edges of the current temporal binning.

        """
        if self._tbins is None:
            self._tbins = self._tbin_func(self.tdistance, self.t_lags, None)

        return self._tbins

    @tbins.setter
    def tbins(self, bins):
        if isinstance(bins, int):
            self._tbins = None
            self._t_lags = bins
        elif isinstance(bins, (list, tuple, np.ndarray)):
            self._tbins = np.asarray(bins)
            self._t_lags = len(self._tbins)
        elif isinstance(bins, str):
            self.set_bin_func(bin_func=bins, axis='time')
        else:
            raise AttributeError('bin value cannot be parsed.')

        # reset the groups
        self._tgroups = None

    @property
    def meshbins(self):
        return np.meshgrid(self.xbins, self.tbins)

    @property
    def estimator(self):
        return self._estimator

    @estimator.setter
    def estimator(self, value):
        self.set_estimator(estimator_name=value)

    def set_estimator(self, estimator_name):
        # reset the fitting
        self.cof, self.cov = None, None

        if isinstance(estimator_name, str):
            if estimator_name.lower() == 'matheron':
                self._estimator = estimators.matheron
            elif estimator_name.lower() == 'cressie':
                self._estimator = estimators.cressie
            elif estimator_name.lower() == 'dowd':
                self._estimator = estimators.dowd
            elif estimator_name.lower() == 'genton':
                self._estimator = estimators.genton
            elif estimator_name.lower() == 'minmax':
                self._estimator = estimators.minmax
            elif estimator_name.lower() == 'percentile':
                self._estimator = estimators.percentile
            elif estimator_name.lower() == 'entropy':
                self._estimator = estimators.entropy
            else:
                raise ValueError(
                    ('Variogram estimator %s is not understood, please' +
                    'provide the function.') % estimator_name
                )
        elif callable(estimator_name):
            self._estimator = estimator_name
        else:
            raise ValueError('The estimator has to be a string or callable.')

    # ------------------------------------------------------------------------ #
    #                         PRE-PROCESSING                                   #
    # ------------------------------------------------------------------------ #
    def lag_groups(self, axis):
        """Lag class group mask array

        Returns a mask array for the given axis (either 'space' or 'time').
        It will have as amany elements as the respective distance matrices.
        **Unlike the base Variogram class, it does not mask the array of
        pairwise differences.**. It will mask the distance matrix of the
        respective axis.

        Parameters
        ----------
        axis : str
            Can either be 'space' or 'time'. Specifies the axis the mask array
            shall be returned for.

        Returns
        -------
        masK_array : numpy.array
            mask array that identifies the lag class group index for each pair
            of points on the given axis.

        """
        if not isinstance(axis, str):
            raise AttributeError('axis has to be of type string.')

        # space axis
        if axis.lower() == 'space' or axis.lower() == 's':
            if self._xgroups is None:
                self._calc_group(axis=axis, force=False)
            return self._xgroups

        # time axis
        elif axis.lower() == 'time' or axis.lower() == 't':
            if self._tgroups is None:
                self._calc_group(axis=axis, force=False)
            return self._tgroups

        else:
            raise ValueError("axis has to be one of 'space', 'time'.")

    def lag_classes(self):
        """Iterator over all lag classes

        Returns an iterator over all lag classes by aligning all time lags
        over all space lags. This means that it will yield all time lag groups
        for a space lag of index 0 at first and then iterate the space lags.

        Returns
        -------
        iterator

        """
        # are differences already calculated
        if self._diff is None:
            self._calc_diff(force=False)

        # get the group masking arrays
        xgrp = self.lag_groups(axis='space')
        tgrp = self.lag_groups(axis='time')

        def diff_select(x, t):
            return self._diff[np.where(xgrp == x)[0]][:, np.where(tgrp == t)[0]]

        # iterate
        for x in range(self.x_lags):
            for t in range(self.t_lags):
                yield diff_select(x, t).flatten()

    def _get_experimental(self):
        # TODO: fix this
        if self.estimator.__name__ == 'entropy':
            raise NotImplementedError

        # this might
        z = np.fromiter(
            (self.estimator(vals) for vals in self.lag_classes()),
            dtype=float
        )

        return z.copy()

    @property
    def experimental(self):
        """Experimental Variogram

        Returns an experimental variogram for the given data. The
        semivariances are arranged over the spatial binning as defined in
        SpaceTimeVariogram.xbins and temporal binning defined in
        SpaceTimeVariogram.tbins.

        Returns
        -------
        variogram : numpy.ndarray
            Returns an two dimensional array of semivariances over space on
            the first axis and time over the second axis.

        """
        return self._get_experimental()

    def __calc_xdist(self, force=False):
        """Calculate distance in space

        Use :func:`xdist_func <skgstat.SpaceTimeVariogram.xdist_func>` to
        calculate the pairwise space distance matrix. The calculation will be
        cached and not recalculated. The recalculation can be forced setting
        ``force=True``.

        Parameters
        ----------
        force : bool
            If True, an eventually cached version of the distance matrix
            will be deleted.

        """
        if self._xdist is None or force:
            self._xdist = self.xdist_func(self._X)

    def __calc_tdist(self, force=False):
        """Calculate distance in time

        Use :func:`tdist_func <skgstat.SpaceTimeVariogram.tdist_func>` to
        calculate the pairwise time distance matrix. The calculation will be
        cached and not recalculated. The recalculation can be forced setting
        ``force=True``.

        Parameters
        ----------
        force : bool
            If True, an eventually cached version of the distance matrix
            will be deleted.

        """
        if self._tdist is None or force:
            # extract the timestamps
            t = np.stack((
                np.arange(self.values.shape[1]),
                [0] * self.values.shape[1]
            ), axis=1)
            self._tdist = self.tdist_func(t)

    def _calc_diff(self, force=False):
        """Calculate pairwise differences

        Calculate the the pairwise differences for all space lag and
        time lag class combinations. The result is stored in the
        SpaceTimeVariogram._diff matrix, which has the form (m, n) with m
        the size of the space distance array and n the size of the time
        distance array.


        Parameters
        ----------
        force : bool
            If True, any calculated and cached result will be deleted and a
            clean calculation will be performed.

        Notes
        -----
        This is a Python only implementation that can get quite slow as any
        added obervation on the space or time axis will increase the matrix
        dimension by one. It is also slow as 4 loops are needed to loop the
        matrix. I am evaluating at the moment if the function performs better
        using numpys vectorizations or by implementing a Cython, Fortran,
        Rust lib that can do the heavy stuff.

        """
        # check the force
        if not force and self._diff is not None:
            return

        # get size of distance matrices
        xn = self.xdistance.size
        tn = self.tdistance.size

        # get outer and inner iterators
        outer, inner = self.values.shape
        v = self.values

        # prepare TODO: here the Fortran, Rust, whatever calc
        self._diff = np.zeros((xn, tn)) * np.nan

        xidx = 0
        for xi in range(outer):
            for xj in range(outer):
                if xi < xj:
                    tidx = 0
                    for ti in range(inner):
                        for tj in range(inner):
                            if ti < tj:
                                self._diff[xidx][tidx] = v[xi, ti] - v[xj, tj]
                                tidx += 1
                    xidx += 1

    def _calc_group(self, axis, force=False):
        """Calculate lag class grouping

        Calculate a lag class grouping mask array for the given axis. The
        axis can be either 'space' or 'time'. The result will be cached
        either in the _sgroups (space) or _tgroups (time) array will match
        the respective distance matrix. The group value indicates the lag
        class index for the matching point pair.
        If force is False (default) and the groups have been calculated,
        no new calculation will be started.

        Parameters
        ----------
        axis : str
            Can be either 'space' for the space lag grouping or 'time' for
            the temporal lag grouping.
        force : bool
            If True, any present cached grouping array will be overwritten.

        Returns
        -------
        void

        """
        # switch the axis
        if axis.lower() == 'space' or axis.lower() == 's':
            grp = self._xgroups
            fmt = 'x'
        elif axis.lower() == 'time' or axis.lower() == 't':
            grp = self._tgroups
            fmt = 't'
        else:
            raise ValueError('Axis %s is not supported' % axis)

        # check the force
        if not force and grp is not None:
            return

        # copy the arrays
        bins = getattr(self, '%sbins' % fmt)
        d = getattr(self, '%sdistance' % fmt)

        # set all groups to -1
        grp = np.ones(len(d), dtype=int) * -1

        # go for the classification
        for i, bounds in enumerate(zip([0] + list(bins), bins)):
            grp[np.where((d > bounds[0]) & (d <= bounds[1]))] = i

        # save
        setattr(self, '_%sgroups' % fmt, grp)

    def preprocessing(self, force=False):
        """Preprocessing

        Start all necessary calculation jobs needed to derive an experimental
        variogram. This hasto be present before the model fitting can be done.
        The force parameter will make all calculation functions to delete all
        cached intermediate results and make a clean calculation.

        Parameters
        ----------
        force : bool
            If True, all cached intermediate results will be deleted and a
            clean calculation will be done.

        """
        # recalculate distances
        self.__calc_xdist(force=force)
        self.__calc_tdist(force=force)
        self._calc_diff(force=force)
        self._calc_group(axis='space', force=force)
        self._calc_group(axis='time', force=force)

    # ------------------------------------------------------------------------ #
    #                              FITTING                                     #
    # ------------------------------------------------------------------------ #

    # ------------------------------------------------------------------------ #
    #                              RESULTS                                     #
    # ------------------------------------------------------------------------ #
    def get_marginal(self, axis, lag=0):
        """Marginal Variogram

        Returns the marginal experimental variogram of axis for the given lag
        on the other axis. Axis can either be 'space' or 'time'. The parameter
        lag specifies the index of the desired lag class on the other axis.

        Parameters
        ----------
        axis : str
            The axis a marginal variogram shall be calculated for. Can either
            be ' space' or 'time'.
        lag : int
            Index of the lag class group on the other axis to be used. In case
            this is 0, this is often considered to be *the* marginal variogram
            of the axis.

        Returns
        -------
        variogram : numpy.array
            Marginal variogram of the given axis

        """
        # check the axis
        if not isinstance(axis, str):
            raise AttributeError('axis has to be of type string.')

        if axis.lower() == 'space' or axis.lower() == 's':
            return np.fromiter(
                (self.estimator(self._get_member(i, lag)) for i in range(self.x_lags)),
                dtype=float
            )
        elif axis.lower() == 'time' or axis.lower() == 't':
            return np.fromiter(
                (self.estimator(self._get_member(lag, j)) for j in range(self.t_lags)),
                dtype=float
            )
        else:
            raise ValueError("axis can either be 'space' or 'time'.")

    def _get_member(self, xlag, tlag):
        x_idxs = self._xgroups == xlag
        t_idxs = self._tgroups == tlag
        return self._diff[np.where(x_idxs)[0]][:, np.where(t_idxs)[0]].flatten()

    # ------------------------------------------------------------------------ #
    #                             PLOTTING                                     #
    # ------------------------------------------------------------------------ #
    def plot(self, kind='scatter', ax=None, **kwargs):
        """Plot the experimental variogram

        At the current version the SpaceTimeVariogram class is not capable of
        modeling a spe-time variogram function, therefore all plots will only
        show the experimental variogram.
        As the experimental space-time semivariance is depending on a space
        and a time lag, one would basically need a 3D scatter plot, which is
        the default plot. However, 3D plots can be, especially for scientific
        usage, a bit problematic. Therefore the plot function can plot a
        variety of 3D and 2D plots.

        Parameters
        ----------
        kind : str
            Has to be one of:

            * **scatter**
            * **surface**
            * **contour**
            * **contourf**
            * **matrix**
            * **marginals**

        ax : matplotlib.AxesSubplot, mpl_toolkits.mplot3d.Axes3D, None
            If None, the function will create a new figure and suitable Axes.
            Else, the Axes object can be passed to plot the variogram into an
            existing figure. In this case, one has to pass the correct type
            of Axes, whether it's a 3D or 2D kind of a plot.
        kwargs : dict
            All keyword arguments are passed down to the actual plotting
            function. Refer to their documentation for a more detailed
            description.

        Returns
        -------
        fig : matplotlib.Figure

        See Also
        --------
        SpaceTimeVariogram.scatter
        SpaceTimeVariogram.surface
        SpaceTimeVariogram.marginals

        """
        # switch the plot kind
        if not isinstance(kind, str):
            raise ValueError('kind has to be of type string.')

        if kind.lower() == 'scatter':
            return self.scatter(ax=ax, **kwargs)
        elif kind.lower() == 'surf' or kind.lower() == 'surface':
            return self.surface(ax=ax, **kwargs)
        elif kind.lower() == 'contour':
            return self.contour(ax=ax)
        elif kind.lower() == 'contourf':
            return self.contourf(ax=ax)
        elif kind.lower() == 'matrix' or kind.lower() == 'mat':
            raise NotImplementedError
        elif kind.lower() == 'marginals':
            return self.marginals(plot=True, axes=ax, **kwargs)
        else:
            raise ValueError('kind %s is not a valid value.')

    def scatter(self, ax=None, elev=30, azim=220, c='g',
                depthshade=True, **kwargs):
        """3D Scatter Variogram

        Plot the experimental variogram into a 3D matplotlib.Figure. The two
        variogram axis (space, time) will span a meshgrid over the x and y axis
        and the semivariance will be plotted as z value over the respective
        space and time lag coordinate.

        Parameters
        ----------
        ax : mpl_toolkits.mplot3d.Axes3D, None
            If ax is None (default), a new Figure and Axes instance will be
            created. If ax is given, this instance will be used for the plot.
        elev : int
            The elevation of the 3D plot, which is a rotation over the xy-plane.
        azim : int
            The azimuth of the 3D plot, which is a rotation over the z-axis.
        c : str
            Color of the scatter points, will be passed to the matplotlib
            ``c`` argument. The function also accepts ``color`` as an alias.
        depthshade : bool
            If True, the scatter points will change their color according to
            the distance from the viewport for illustration reasons.
        kwargs : dict
            Other kwargs accepted are only ``color`` as an alias for ``c``
            and ``figsize``, if ax is None. Anything else will be ignored.

        Returns
        -------
        fig : matplotlib.Figure

        Examples
        --------
        In case an ax shall be passed to the function, note that this plot
        requires an AxesSubplot, that is capable of creating a 3D plot. This
        can be done like:

        .. code-block:: python

            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.pyplot as plt
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # STV is an instance of SpaceTimeVariogram
            STV.scatter(ax=ax)

        See Also
        --------
        SpaceTimeVariogram.surface

        """
        return self._plot3d(kind='scatter', ax=ax, elev=elev, azim=azim,
                            c=c, depthshade=depthshade, **kwargs)

    def surface(self, ax=None, elev=30, azim=220, color='g',
                alpha=0.5, **kwargs):
        """3D Scatter Variogram

        Plot the experimental variogram into a 3D matplotlib.Figure. The two
        variogram axis (space, time) will span a meshgrid over the x and y axis
        and the semivariance will be plotted as z value over the respective
        space and time lag coordinate. Unlike
        :func:`scatter <skgstat.SpaceTimeVariogram.scatter>` the semivariance
        will not be scattered as points but rather as a surface plot. The
        surface is approximated by (Delauney) triangulation of the z-axis.

        Parameters
        ----------
        ax : mpl_toolkits.mplot3d.Axes3D, None
            If ax is None (default), a new Figure and Axes instance will be
            created. If ax is given, this instance will be used for the plot.
        elev : int
            The elevation of the 3D plot, which is a rotation over the xy-plane.
        azim : int
            The azimuth of the 3D plot, which is a rotation over the z-axis.
        color : str
            Color of the scatter points, will be passed to the matplotlib
            ``color`` argument. The function also accepts ``c`` as an alias.
        alpha : float
            Sets the transparency of the surface as 0 <= alpha <= 1, with 0
            being completely transparent.
        kwargs : dict
            Other kwargs accepted are only ``color`` as an alias for ``c``
            and ``figsize``, if ax is None. Anything else will be ignored.

        Returns
        -------
        fig : matplotlib.Figure

        Notes
        -----
        In case an ax shall be passed to the function, note that this plot
        requires an AxesSubplot, that is capable of creating a 3D plot. This
        can be done like:

        .. code-block:: python

            from mpl_toolkits.mplot3d import Axes3D
            import matplotlib.pyplot as plt
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # STV is an instance of SpaceTimeVariogram
            STV.surface(ax=ax)

        See Also
        --------
        SpaceTimeVariogram.scatter

        """
        return self._plot3d(kind='surf', ax=ax, elev=elev, azim=azim,
                            color=color, alpha=alpha, **kwargs)

    def _plot3d(self, kind='scatter', ax=None, elev=30, azim=220, **kwargs):
        # Create or check the Figure and Axes
        if ax is not None:
            if not isinstance(ax, Axes3D):
                raise ValueError('The passed ax object is not an instance '
                                 'of mpl_toolkis.mplot3d.Axes3D.')
            fig = ax.get_figure()
        else:
            fig = plt.figure(figsize=kwargs.get('figsize', (10, 10)))
            ax = fig.add_subplot(111, projection='3d')

        # get the data, spanned over a bin meshgrid
        xx, yy = self.meshbins
        z = self.experimental
        x = xx.flatten()
        y = yy.flatten()

        # plot
        c = kwargs.get('color', 'g') if 'color' in kwargs else kwargs.get('c', 'g')

        ax.view_init(elev=elev, azim=azim)
        if kind == 'surf':
            ax.plot_trisurf(x, y, z, color=c, alpha=kwargs.get('alpha', 0.8))
        elif kind == 'scatter':
            ax.scatter(x, y, z, c=c, depthshade=kwargs.get('depthshade', False))
        else:
            raise ValueError('%s is not a valid 3D plot' % kind)

        # set the labels
        ax.set_xlabel('space')
        ax.set_ylabel('time')
        ax.set_zlabel('semivariance [%s]' % self.estimator.__name__)

        # return
        return fig

    def contour(self, ax=None, zoom_factor=100., levels=10, colors='k',
                linewidths=0.3, method="fast", **kwargs):
        """Variogram 2D contour plot

        Plot a 2D contour plot of the experimental variogram. The
        experimental semi-variance values are spanned over a space - time lag
        meshgrid. This grid is (linear) interpolated onto the given
        resolution for visual reasons. Then, contour lines are caluclated
        from the denser grid. Their number can be specified by *levels*.

        Parameters
        ----------
        ax : matplotlib.AxesSubplot, None
            If None a new matplotlib.Figure will be created, otherwise the
            plot will be rendered into the given subplot.
        resolution : tuple
            The experimental variogram will be interpolated onto a regular
            grid for visual reasons. The density of this plot can be set by
            resolution as a tuple: (space_dim, time_dim). High resolutions
            result in smoother contours, but are expansive in calculation time.
        levels : int
            Number of levels to be formed for finding contour lines. More
            levels result in more detailed plots, but are expansive in terms
            of calculation time.
        colors : str, list
            Will be passed down to matplotlib.pyplot.contour as *c* parameter.
        linewidths : float, list
            Will be passed down to matplotlib.pyplot.contour as *linewidths*
            parameter.
        kwargs : dict
            Other arguments that can be specific to *contour* or *contourf*
            type. Accepts *xlabel*, *ylabel*, *xlim* and *ylim* as of this
            writing.

        Returns
        -------
        fig : matplotlib.Figure
            The Figure object used for rendering the contour plot.

        See Also
        --------
        SpaceTimeVariogram.contourf

        """
        return self._plot2d(kind='contour', ax=ax, zoom_factor=zoom_factor,
                            levels=levels, colors=colors, method=method,
                            linewidths=linewidths, **kwargs)

    def contourf(self, ax=None, zoom_factor=100., levels=10,
                 cmap='RdYlBu_r', method="fast", **kwargs):
        """Variogram 2D filled contour plot

        Plot a 2D filled contour plot of the experimental variogram. The
        experimental semi-variance values are spanned over a space - time lag
        meshgrid. This grid is (linear) interpolated onto the given
        resolution for visual reasons. Then, contour lines are caluclated
        from the denser grid. Their number can be specified by *levels*.
        Finally, each contour region is filled with a color supplied by the
        specified *cmap*.

        Parameters
        ----------
        ax : matplotlib.AxesSubplot, None
            If None a new matplotlib.Figure will be created, otherwise the
            plot will be rendered into the given subplot.
        resolution : tuple
            The experimental variogram will be interpolated onto a regular
            grid for visual reasons. The density of this plot can be set by
            resolution as a tuple: (space_dim, time_dim). High resolutions
            result in smoother contours, but are expansive in calculation time.
        levels : int
            Number of levels to be formed for finding contour lines. More
            levels result in more detailed plots, but are expansive in terms
            of calculation time.
        cmap : str
            Will be passed down to matplotlib.pyplot.contourf as *cmap*
            parameter. Can be any valid color range supported by matplotlib.
        kwargs : dict
            Other arguments that can be specific to *contour* or *contourf*
            type. Accepts *xlabel*, *ylabel*, *xlim* and *ylim* as of this
            writing.

        Returns
        -------
        fig : matplotlib.Figure
            The Figure object used for rendering the contour plot.

        See Also
        --------
        SpaceTimeVariogram.contour

        """
        return self._plot2d(kind='contourf', ax=ax, zoom_factor=zoom_factor,
                            levels=levels, cmap=cmap, method=method, **kwargs)

    def _plot2d(self, kind='contour', ax=None, zoom_factor=100.,
                levels=10, method="fast", **kwargs):
        # get or create the figure
        if ax is not None:
            fig = ax.get_figure()
        else:
            fig, ax = plt.subplots(1, 1, figsize=kwargs.get('figsize', (8, 8)))

        # prepare the meshgrid
        xx, yy = self.meshbins
        z = self.experimental
        x = xx.flatten()
        y = yy.flatten()

        # interpolation, either fast or precise
        if method.lower() == "fast":
            zi = zoom(z.reshape((self.x_lags, self.t_lags)), zoom_factor,
                      order=1, prefilter=False)
        elif method.lower() == "precise":
            # zoom the meshgrid by linear interpolation
            xxi = zoom(xx, zoom_factor, order=1)
            yyi = zoom(yy, zoom_factor, order=1)

            # interpolate the semivariance
            zi = griddata((x, y), z, (xxi, yyi), method='linear')
        else:
            raise ValueError("method has to be one of ['fast', 'precise']")

        # get the bounds
        zmin = np.nanmin(zi)
        zmax = np.nanmax(zi)

        # get the plotting parameters
        lev = np.linspace(0, zmax, levels)
        c = kwargs.get('color') if 'color' in kwargs else kwargs.get('c', 'k')
        cmap = kwargs.get('cmap', 'RdYlBu_r')

        # plot
        if kind.lower() == 'contour':
            ax.contour(zi.T, colors=c, levels=lev, vmin=zmin * 1.1,
                       vmax=zmax * 0.9, linewidths=kwargs.get('linewidths', 0.3)
                       )
        elif kind.lower() == 'contourf':
            C = ax.contourf(zi.T, cmap=cmap, levels=lev, vmin=zmin * 1.1,
                            vmax=zmax * 0.9)
            if kwargs.get('colorbar', True):
                ax.colorbar(C, ax=ax)
        else:
            raise ValueError("%s is not a valid 2D plot" % kind)

        # the grid is interpolated, set the bins as ticks
        ax.set_xticks(self.xbins)
        ax.set_xticklabels(
            [kwargs.get('xfmt', '%.1f') % b for b in self.xbins])
        ax.set_yticks(self.tbins)
        ax.set_yticklabels(
            [kwargs.get('yfmt', '%.1f') % b for b in self.tbins]
        )

        # some labels
        ax.set_xlabel(kwargs.get('xlabel', 'space'))
        ax.set_ylabel(kwargs.get('ylabel', 'time'))
        ax.set_xlim(kwargs.get('xlim', (0, zi.shape[0])))
        ax.set_ylim(kwargs.get('ylim', (0, zi.shape[1])))

        return fig

    def marginals(self, plot=True, axes=None, sharey=True, **kwargs):
        """Plot marginal variograms

        Plots the two marginal variograms into a new or existing figure. The
        space marginal variogram is defined to be the variogram of temporal
        lag class 0, while the time marginal variogram uses only spatial lag
        class 0. In case the expected variability is not of same magnitude,
        the sharey parameter should be set to ``False`` in order to use
        separated y-axes.

        Parameters
        ----------
        plot : bool
            If set to False, no matplotlib.Figure will be returned. Instead a
            tuple of the two marginal experimental variogram values is
            returned.
        axes : list
            Is either ``None`` to create a new matplotlib.Figure. Otherwise
            it has to be a list of two matplotlib.AxesSubplot instances,
            which will then be used for plotting.
        sharey : bool
            If True (default), the two marginal variograms will share their
            y-axis to increase comparability. Should be set to False in the
            variances are of different magnitude.
        kwargs : dict
            Only kwargs accepted is  ``figsize``, if ax is None.
            Anything else will be ignored.

        Returns
        -------
        variograms : tuple
            If plot is False, a tuple of numpy.arrays are returned. These are
            the two experimental marginal variograms.
        plots : matplotlib.Figure
            If plot is True, the matplotlib.Figure will be returned.

        """
        # get the marginal space variogram
        vx = self.get_marginal(axis='space', lag=0)
        vy = self.get_marginal(axis='time', lag=0)

        # if no plot is desired, return the experimental variograms
        if not plot:
            return vx, vy

        # check if an ax needs to be created
        if axes is None:
            fig, axes = plt.subplots(1, 2,
                                     figsize=kwargs.get('figsize', (12, 6)),
                                     sharey=sharey
                                     )
        else:
            if len(axes) != 2:
                raise ValueError('axes needs to an array of two AxesSubplot '
                                 'objects')
            fig = axes[0].get_figure()

        # plot
        ax = axes[0]
        ax2 = axes[1]
        ax3 = ax2.twinx()
        ax3.get_shared_y_axes().join(ax3, ax)
        ax.plot(self.xbins, vx, '-ob')
        ax3.plot(self.tbins, vy, '-og')

        # set labels
        ax.set_xlabel('distance [spatial]')
        ax.set_ylabel('semivariance [%s]' % self.estimator.__name__)
        ax2.set_xlabel('distance [temporal]')
        if not sharey:
            ax3.set_ylabel('semivariance [%s]' % self.estimator.__name__)

        # set title and grid
        ax.set_title('spatial marginal variogram')
        ax2.set_title('temporal marginal variogram')

        ax.grid(which='major')
        ax2.grid(which='major')
        plt.tight_layout()

        # return
        return fig
