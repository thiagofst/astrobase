'''hatpilc.py - Waqas Bhatti (wbhatti@astro.princeton.edu) - May 2017
License: MIT. See LICENSE for full text.

This is mostly for internal use. Contains functions to read text light curves
produced by the HATPI prototype system's image-subtraction photometry pipeline.

'''

####################
## SYSTEM IMPORTS ##
####################

import logging
from datetime import datetime
from traceback import format_exc
import os
import os.path
import gzip
import re
import glob
import sys

try:
    import cPickle as pickle
except:
    import pickle

import numpy as np



#############
## LOGGING ##
#############

# setup a logger
LOGGER = None

def set_logger_parent(parent_name):
    globals()['LOGGER'] = logging.getLogger('%s.hatpilc' % parent_name)

def LOGDEBUG(message):
    if LOGGER:
        LOGGER.debug(message)
    elif DEBUG:
        print('%sZ [DBUG]: %s' % (datetime.utcnow().isoformat(), message))

def LOGINFO(message):
    if LOGGER:
        LOGGER.info(message)
    else:
        print('%sZ [INFO]: %s' % (datetime.utcnow().isoformat(), message))

def LOGERROR(message):
    if LOGGER:
        LOGGER.error(message)
    else:
        print('%sZ [ERR!]: %s' % (datetime.utcnow().isoformat(), message))

def LOGWARNING(message):
    if LOGGER:
        LOGGER.warning(message)
    else:
        print('%sZ [WRN!]: %s' % (datetime.utcnow().isoformat(), message))

def LOGEXCEPTION(message):
    if LOGGER:
        LOGGER.exception(message)
    else:
        print(
            '%sZ [EXC!]: %s\nexception was: %s' % (
                datetime.utcnow().isoformat(),
                message, format_exc()
                )
            )



###################
## USEFUL CONFIG ##
###################

# used to find HATIDs
HATIDREGEX = re.compile(r'HAT-\d{3}-\d{7}')

# used to get the station ID, frame number, subframe id, and CCD number from a
# framekey or standard HAT FITS filename
FRAMEREGEX = re.compile(r'(\d{1})\-(\d{6})(\w{0,1})_(\d{1})')

# these are the columns in the input text LCs, common to all epdlc and tfalcs
# an additional column for the TFA magnitude in the current aperture is added
# for tfalcs. there are three tfalcs for each epdlc, one for each aperture.
COLDEFS = [('rjd',float),  # The reduced Julian date
           ('frk',str),    # Framekey: {stationid}-{framenum}{framesub}_{ccdnum}
           ('hat',str),    # The HATID of the object
           ('xcc',float),  # Original x coordinate on the imagesub astromref
           ('ycc',float),  # Original y coordinate on the imagesub astromref
           ('xic',float),  # Shifted x coordinate on this frame
           ('yic',float),  # Shifted y coordinate on this frame
           ('fsv',float),  # Measured S value
           ('fdv',float),  # Measured D value
           ('fkv',float),  # Measured K value
           ('bgv',float),  # Background value
           ('bge',float),  # Background measurement error
           ('ifl1',float), # Flux measurement in ADU, aperture 1
           ('ife1',float), # Flux error in ADU, aperture 1
           ('irm1',float), # Instrumental magnitude in aperture 1
           ('ire1',float), # Instrumental magnitude error for aperture 1
           ('irq1',str),   # Instrumental magnitude quality flag for aperture 1
           ('ifl2',float), # Flux measurement in ADU, aperture 2
           ('ife2',float), # Flux error in ADU, aperture 2
           ('irm2',float), # Instrumental magnitude in aperture 2
           ('ire2',float), # Instrumental magnitude error for aperture 2
           ('irq2',str),   # Instrumental magnitude quality flag for aperture 2
           ('ifl3',float), # Flux measurement in ADU, aperture 3
           ('ife3',float), # Flux error in ADU, aperture 3
           ('irm3',float), # Instrumental magnitude in aperture 3
           ('ire3',float), # Instrumental magnitude error for aperture 3
           ('irq3',str),   # Instrumental magnitude quality flag for aperture 3
           ('iep1',float), # EPD magnitude for aperture 1
           ('iep2',float), # EPD magnitude for aperture 2
           ('iep3',float)] # EPD magnitude for aperture 3

# these are the mag columns
MAGCOLS = ['ifl1','irm1','iep1',
           'ifl2','irm2','iep2',
           'ifl3','irm3','iep3']

##################################
## READING AND WRITING TEXT LCS ##
##################################

def read_hatpi_textlc(lcfile):
    '''
    This reads in a textlc that is complete up to the TFA stage.

    '''

    if 'TF1' in lcfile:
        thiscoldefs = COLDEFS + [('itf1',float)]
    elif 'TF2' in lcfile:
        thiscoldefs = COLDEFS + [('itf2',float)]
    elif 'TF3' in lcfile:
        thiscoldefs = COLDEFS + [('itf3',float)]

    LOGINFO('reading %s' % lcfile)

    with gzip.open(lcfile,'r') as infd:

        lclines = infd.read().decode().split('\n')
        lclines = [x.split() for x in lclines if ('#' not in x and len(x) > 0)]
        ndet = len(lclines)

        if ndet > 0:

            lccols = list(zip(*lclines))
            lcdict = {x[0]:y for (x,y) in zip(thiscoldefs, lccols)}

            # convert to ndarray
            for col in thiscoldefs:
                lcdict[col[0]] = np.array([col[1](x) for x in lcdict[col[0]]])

        else:

            lcdict = {}
            LOGWARNING('no detections in %s' % lcfile)
            # convert to empty ndarrays
            for col in thiscoldefs:
                lcdict[col[0]] = np.array([])

        # add the object's name to the lcdict
        hatid = HATIDREGEX.findall(lcfile)
        lcdict['objectid'] = hatid[0] if hatid else 'unknown object'

        # add the columns to the lcdict
        lcdict['columns'] = [x[0] for x in thiscoldefs]

        # add some basic info similar to usual HATLCs
        lcdict['objectinfo'] = {
            'ndet':ndet,
            'hatid':hatid[0] if hatid else 'unknown object',
            'network':'HP',
        }

        # break out the {stationid}-{framenum}{framesub}_{ccdnum} framekey
        # into separate columns
        framekeyelems = FRAMEREGEX.findall('\n'.join(lcdict['frk']))

        lcdict['stf'] = np.array([(int(x[0]) if x[0].isdigit() else np.nan)
                                  for x in framekeyelems])
        lcdict['cfn'] = np.array([(int(x[1]) if x[0].isdigit() else np.nan)
                                  for x in framekeyelems])
        lcdict['cfs'] = np.array([x[2] for x in framekeyelems])
        lcdict['ccd'] = np.array([(int(x[3]) if x[0].isdigit() else np.nan)
                                  for x in framekeyelems])

        # update the column list with these columns
        lcdict['columns'].extend(['stf','cfn','cfs','ccd'])

        # add more objectinfo: 'stations', etc.
        lcdict['objectinfo']['stations'] = np.unique(lcdict['stf']).tolist()


    return lcdict



def lcdict_to_pickle(lcdict, outfile=None):
    '''This just writes the lcdict to a pickle.

    If outfile is None, then will try to get the name from the
    lcdict['objectid'] and write to <objectid>-hptxtlc.pkl. If that fails, will
    write to a file named hptxtlc.pkl'.

    '''

    if not outfile and lcdict['objectid']:
        outfile = '%s-hptxtlc.pkl' % lcdict['objectid']
    elif not outfile and not lcdict['objectid']:
        outfile = 'hptxtlc.pkl'

    with open(outfile,'wb') as outfd:
        pickle.dump(lcdict, outfd, protocol=pickle.HIGHEST_PROTOCOL)

    if os.path.exists(outfile):
        LOGINFO('lcdict for object: %s -> %s OK' % (lcdict['objectid'],
                                                    outfile))
        return outfile
    else:
        LOGERROR('could not make a pickle for this lcdict!')
        return None



def read_hatpi_pklc(lcfile):
    '''
    This just reads a pickle LC. Returns an lcdict.

    '''

    try:
        with open(lcfile,'rb') as infd:
            lcdict = pickle.load(infd)

        return lcdict

    except UnicodeDecodeError:

        with open(lcfile,'rb') as infd:
            lcdict = pickle.load(infd, encoding='latin1')

        LOGWARNING('pickle %s was probably from Python 2 '
                   'and failed to load without using "latin1" encoding. '
                   'This is probably a numpy issue: '
                   'http://stackoverflow.com/q/11305790' % lcfile)

        return lcdict




################################
## CONCATENATING LIGHT CURVES ##
################################

def concatenate_textlcs(lclist,
                        sortby='rjd',
                        normalize=True,
                        normto=None):
    '''This concatenates a list of light curves.

    Does not care about overlaps or duplicates. The light curves must all be
    from the same aperture.

    The intended use is to concatenate light curves across CCDs or instrument
    changes for a single object. These can then be normalized later using
    standard astrobase tools to search for variablity and/or periodicity.

    sortby is a column to sort the final concatenated light curve by in
    ascending order.

    If normalize is True, then each light curve's magnitude columns are
    normalized to zero, and the whole light curve is then normalized to the
    global median magnitude for each magnitude column.

    If normto == 'globalmedian', will add back the global median values to the
    light curve.

    '''

    # read the first light curve
    lcdict = read_hatpi_textlc(lclist[0])

    # track which LC goes where
    # initial LC
    lccounter = 0
    lcdict['concatenated'] = {lccounter: lclist[0]}
    lcdict['lcn'] = np.full_like(lcdict['rjd'], lccounter)

    # now read the rest
    for lcf in lclist[1:]:

        thislcd = read_hatpi_textlc(lcf)

        # if the columns don't agree, skip this LC
        if thislcd['columns'] != lcdict['columns']:
            LOGERROR('file %s does not have the '
                     'same columns as first file %s, skipping...'
                     % (lcf, lclist[0]))
            continue

        # otherwise, go ahead and start concatenatin'
        else:

            LOGINFO('adding %s (ndet: %s) to %s (ndet: %s)'
                    % (lcf,
                       thislcd['objectinfo']['ndet'],
                       lclist[0],
                       lcdict[lcdict['columns'][0]].size))

            # update LC tracking
            lccounter = lccounter + 1
            lcdict['concatenated'][lccounter] = lcf
            lcdict['lcn'] = np.concatenate((
                lcdict['lcn'],
                np.full_like(thislcd['rjd'],lccounter)
            ))

            # concatenate the columns
            for col in lcdict['columns']:
                lcdict[col] = np.concatenate((lcdict[col], thislcd[col]))

    #
    # now we're all done concatenatin'
    #

    # make sure to add up the ndet
    lcdict['objectinfo']['ndet'] = lcdict[lcdict['columns'][0]].size

    # update the stations
    lcdict['objectinfo']['stations'] = np.unique(lcdict['stf']).tolist()

    # update the total LC count
    lcdict['nconcatenated'] = lccounter + 1

    # if we're supposed to sort by a column, do so
    if sortby and sortby in [x[0] for x in COLDEFS]:

        LOGINFO('sorting concatenated light curve by %s...' % sortby)
        sortind = np.argsort(lcdict[sortby])
        # sort all the columns by this index
        for col in lcdict['columns']:
            lcdict[col] = lcdict[col][sortind]


    # if we're supposed to normalize, do it by LC
    if normalize:

        LOGINFO('normalizing concatenated light curve...')

        # this tracks median mag for each LC
        medianmags = {x:[] for x in MAGCOLS}

        for lcind in range(lcdict['nconcatenated']):

            for col in MAGCOLS:

                LOGINFO('normalizing %s for LC index: %s' % (col, lcind))

                thismedval = np.nanmedian(lcdict[col][lcdict['lcn'] == lcind])
                medianmags[col].append(thismedval)

                # handle fluxes
                if col in ('ifl1','ifl2','ifl3'):

                    lcdict[col][lcdict['lcn'] == lcind] = (
                        lcdict[col][lcdict['lcn'] == lcind] /
                        thismedval
                    )

                else:

                    lcdict[col][lcdict['lcn'] == lcind] = (
                        lcdict[col][lcdict['lcn'] == lcind] -
                        thismedval
                    )


        if normto == 'globalmedian':
            # now that everything is normalized to zero, we need to add back the
            # global median value for each column across all light curves
            for col in MAGCOLS:

                # handle fluxes
                if col in ('ifl1','ifl2','ifl3'):

                    lcdict[col] = lcdict[col] * np.median(medianmags[col])

                else:

                    lcdict[col] = lcdict[col] + np.median(medianmags[col])


    LOGINFO('done. concatenated light curve has %s detections' %
            lcdict['objectinfo']['ndet'])
    return lcdict



def concatenate_textlcs_for_objectid(lcbasedir,
                                     objectid,
                                     aperture='TF1',
                                     sortby='rjd',
                                     normalize=True,
                                     normto=None):
    '''This concatenates all text LCs for an objectid with the given aperture.

    Does not care about overlaps or duplicates. The light curves must all be
    from the same aperture.

    The intended use is to concatenate light curves across CCDs or instrument
    changes for a single object. These can then be normalized later using
    standard astrobase tools to search for variablity and/or periodicity.


    lcbasedir is the directory to start searching in.

    objectid is the object to search for.

    aperture is the aperture postfix to use: (TF1 = aperture 1,
                                              TF2 = aperture 2,
                                              TF3 = aperture 3)

    sortby is a column to sort the final concatenated light curve by in
    ascending order.

    If normalize is True, then each light curve's magnitude columns are
    normalized to zero, and the whole light curve is then normalized to the
    global median magnitude for each magnitude column.

    If normto == 'globalmedian', will add back the global median values to the
    light curve.

    '''
    LOGINFO('looking for light curves for %s, aperture %s in directory: %s'
            % (objectid, aperture, lcbasedir))

    # use recursive glob for Python 3.5+
    if sys.version_info[:2] > (3,4):

        matching = glob.glob(os.path.join(lcbasedir,
                                          '**',
                                          '*%s*%s*' % (objectid, aperture)),
                             recursive=True)
        LOGINFO('found %s files: %s' % (len(matching), repr(matching)))

    # otherwise, use os.walk and glob
    else:

        # use os.walk to go through the directories
        walker = os.walk(lcbasedir)
        matching = []

        for root, dirs, files in walker:
            for sdir in dirs:
                searchpath = os.path.join(root,
                                          sdir,
                                          '*%s*%s*' % (objectid, aperture))
                foundfiles = glob.glob(searchpath)

                if foundfiles:
                    matching.extend(foundfiles)
                    LOGINFO('found %s in dir: %s' % (repr(foundfiles),
                                                     os.path.join(root,sdir)))

    # now that we have all the files, concatenate them
    if matching and len(matching) > 1:
        clcdict = concatenate_textlcs(matching,
                                      sortby=sortby,
                                      normalize=normalize,
                                      normto=normto)
        return clcdict
    elif matching and len(matching) == 1:
        return read_hatpi_textlc(matching[0])
    else:
        LOGERROR('did not find any light curves for %s and aperture %s' %
                 (objectid, aperture))
        return None



def concat_write_pklc(lcbasedir,
                      objectid,
                      aperture='TF1',
                      outdir=None):
    '''
    This concatenates all text LCs for the given object and writes to a pklc.

    '''

    lcdict = concatenate_textlcs_for_objectid(lcbasedir,
                                              objectid,
                                              aperture=aperture)
    if not outdir:
        outdir = 'pklcs'
        if not os.path.exists(outdir):
            os.mkdir(outdir)

    outfpath = os.path.join(outdir, '%s-pklc.pkl' % lcdict['objectid'])
    pklc = lcdict_to_pickle(lcdict, outfile=outfpath)