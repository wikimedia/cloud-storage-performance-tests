import { IconButton, makeStyles } from '@material-ui/core';
import clsx from 'clsx';
import React from 'react';
import { useEffect, useState } from 'react';
import { ReportT } from '../../types';
import { ReportDetails } from '../ReportDetails';
import ChevronLeftIcon from '@material-ui/icons/ChevronLeft';
import ChevronRightIcon from '@material-ui/icons/ChevronRight';
import Divider from '@material-ui/core/Divider';

const drawerWidth = 350;

const useStyles = makeStyles(() => ({
    root: {
        display: 'flex',
    },
    toolbar: {
        paddingRight: 24, // keep right padding when drawer closed
    },
    reportsList: {
        height: '100%',
        width: '100%',
        display: 'flex',
        flexDirection: 'row',
    },
    reportsSidebar: {
        display: 'flex',
        flexDirection: 'column',
        width: '400px',
    },
    reportBullets: {
        display: 'flex',
        flexDirection: 'column',
        width: '400px',
    },
    reportsListTitle: {
        fontSize: 'large',
        fontWeight: 'bold',
        textAlign: 'center',
        backgroundColor: 'dimgray',
    },
    reportEntryName: {
        textAlign: 'left',
        '&:hover': {
            textAlign: 'left',
            backgroundColor: 'blue',
        },
    },
    reportEntryNameSelected: {
        textAlign: 'left',
        backgroundColor: 'rgb(0, 0, 134)',
    },
    iconButton: {
        color: '#fff',
        backgroundColor: '#373737',
    },
    toolbarIcon: {
        padding: '0 8px',
    },
    openDrawer: {
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        textAlign: 'center',
    },
    drawerTitle: {
        width: '100%',
        fontSize: '20px',
        fontWeight: 'bold',
    },
    drawerOpen: {
        zIndex: 8,
        width: drawerWidth,
        color: 'rgb(231, 231, 231)',
        backgroundColor: '#373737',
    },
    drawerClosed: {
        zIndex: 8,
        color: 'rgb(231, 231, 231)',
        backgroundColor: '#373737',
        width: '50px',
    },
}));

export function ReportsList(): JSX.Element {
    const classes = useStyles();
    const [reports, setReports] = useState<Array<ReportT>>([]);
    const [report, setReport] = useState<ReportT>();
    const [open, setOpen] = React.useState(true);
    const [loading, setLoading] = React.useState(false);
    const handleDrawerOpen = () => {
        setOpen(true);
    };
    const handleDrawerClose = () => {
        setOpen(false);
    };

    const handleReportSelected = (iter_report: ReportT) => {
        return () => {
            setLoading(true);
            setReport(iter_report);
            setOpen(false);
            setTimeout(() => {
                setLoading(false);
            }, 500);
        };
    };

    useEffect(() => {
        fetch('api/v1/reports/')
            .then((res) => res.json())
            .then((data) => {
                setReports(data);
            });
    }, []);

    return (
        <div className={classes.reportsList}>
            <div className={classes.drawerClosed} hidden={open} onClick={handleDrawerOpen}>
                <IconButton onClick={handleDrawerOpen} className={classes.iconButton} disableRipple={true}>
                    <ChevronRightIcon />
                </IconButton>
            </div>
            <div className={clsx(classes.drawerOpen)} hidden={!open} onClick={handleDrawerClose} >
                <div className={classes.openDrawer}>
                    <IconButton onClick={handleDrawerClose} className={classes.iconButton} disableRipple={true}>
                        <ChevronLeftIcon />
                    </IconButton>
                    <div className={classes.drawerTitle}>Available reports</div>
                </div>
                <div className={classes.reportBullets}>
                    <Divider />
                    {open ? (
                        reports
                            .sort((a, b) => (a.name > b.name ? -1 : 1))
                            .map((iter_report) => {
                                return (
                                    <div
                                        className={
                                            report && iter_report.url === report.url
                                                ? classes.reportEntryNameSelected
                                                : classes.reportEntryName
                                        }
                                        key={iter_report.url}
                                        onClick={handleReportSelected(iter_report)}
                                    >
                                        {iter_report.name}{' '}
                                    </div>
                                );
                            })
                    ) : (
                        <div />
                    )}
                </div>
            </div>
            <ReportDetails report={report} loading={loading} />
        </div>
    );
}
