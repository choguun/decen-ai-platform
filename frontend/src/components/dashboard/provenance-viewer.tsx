'use client'

import React, { useState, useEffect } from 'react';
import axios, { isAxiosError } from 'axios';
import { useAccount } from 'wagmi';
import { toast } from 'sonner';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getAuthToken } from "@/components/auth/connect-wallet-button";
import { Loader2, ExternalLink, X, Copy } from 'lucide-react';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const ipfsGateway = 'https://files.lighthouse.storage/viewFile/';
const filecoinExplorerTx = 'https://calibration.filscan.io/en/message/'; // Explorer URL
const lighthouseGateway = 'https://gateway.lighthouse.storage/ipfs/';

// Update interface to match backend AssetRecord Pydantic model
interface AssetRecord {
  owner: string;
  assetType: string;
  name: string;
  filecoinCid: string;
  metadataCid?: string | null;
  sourceAssetCid?: string | null;
  timestamp: number;
  txHash: string; // Added txHash
}

// Type for preview data (same as TrainModel)
interface PreviewData {
    headers: string[];
    rows: string[][];
}

export function ProvenanceViewer() {
  const { address, isConnected } = useAccount();
  const [provenanceRecords, setProvenanceRecords] = useState<AssetRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // --- Preview State ---
  const [previewCid, setPreviewCid] = useState<string | null>(null); // Which CID is being previewed
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);

  // --- Function to copy CID to clipboard ---
  const handleCopyCid = async (cid: string | undefined | null) => {
    if (!cid) {
      toast.error("Cannot copy empty CID.");
      return;
    }
    try {
      await navigator.clipboard.writeText(cid);
      toast.success("CID copied to clipboard!");
    } catch (err) {
      console.error('Failed to copy CID: ', err);
      toast.error("Failed to copy CID to clipboard.");
    }
  };

  const fetchProvenanceData = async () => {
    const token = getAuthToken();
    if (!token || !isConnected || !address) {
      setProvenanceRecords([]);
      setError(isConnected ? "Authentication token not found. Please re-authenticate." : "Please connect your wallet.");
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${backendUrl}/provenance/mine`, { 
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (Array.isArray(response.data.records)) { 
        setProvenanceRecords(response.data.records); 
        if (response.data.records.length === 0) {
             toast.info("No provenance records found for your address.");
        }
      } else {
        console.error("Unexpected response format from /provenance/mine:", response.data);
        throw new Error("Received invalid data format from server.");
      }
    } catch (error: unknown) {
      console.error("Fetch provenance error:", error);
      let detail = "Failed to fetch provenance records.";
      if (isAxiosError(error)) {
        detail = error.response?.data?.detail || error.message;
      } else if (error instanceof Error) {
        detail = error.message;
      }
      setError(detail);
      toast.error(detail);
      setProvenanceRecords([]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- Function to handle Dataset Preview from Lighthouse --- 
  const handlePreviewDataset = async (cid: string) => {
      if (!cid) {
          toast.error("Invalid CID provided for preview.");
          return;
      }
      if (previewCid === cid) { // If already previewing this CID, close it
          closePreview();
          return;
      }

      setPreviewCid(cid);
      setIsPreviewLoading(true);
      setPreviewError(null);
      setPreviewData(null);
      
      const gatewayUrl = `${lighthouseGateway}${cid}`;
      
      try {
          const response = await fetch(gatewayUrl);
          if (!response.ok) {
              throw new Error(`Failed to fetch from gateway: ${response.status} ${response.statusText}`);
          }
          const csvText = await response.text();
          
          // Basic CSV Parsing
          const lines = csvText.trim().split('\n');
          if (lines.length === 0) {
              setPreviewData({ headers: [], rows: [] });
              setIsPreviewLoading(false);
              return;
          }
          
          const headers = lines[0].split(',').map(h => h.trim());
          const rows = lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));
          
          setPreviewData({ headers, rows });
          toast.success("Dataset preview loaded.");
          
      } catch (error: unknown) {
           console.error(`Dataset preview error for CID ${cid}:`, error);
           let detail = "Failed to load dataset preview." + (error instanceof Error ? ` ${error.message}` : '')
           setPreviewError(detail);
           setPreviewData(null); // Clear data on error
           toast.error(detail);
      } finally {
           setIsPreviewLoading(false);
      }
  };

  // --- Function to close preview --- 
  const closePreview = () => {
      setPreviewCid(null);
      setPreviewData(null);
      setPreviewError(null);
      setIsPreviewLoading(false);
  };

  useEffect(() => {
    if (isConnected && address) {
        fetchProvenanceData();
    } else {
        // Clear data and set appropriate message if disconnected
        setProvenanceRecords([]);
        setError(null); // Clear previous errors
        if (!isConnected) {
             // Optionally set a non-error message like "Connect wallet to view records"
        }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, address]); // Rerun if connection state or address changes

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  const renderCidLink = (cid: string | undefined | null) => {
      if (!cid) return 'N/A';
      const truncated = `${cid.substring(0, 6)}...${cid.substring(cid.length - 4)}`;
      return (
          <a href={`${ipfsGateway}${cid}`} target="_blank" rel="noopener noreferrer" title={cid} className="inline-flex items-center gap-1 hover:underline">
              {truncated}
              <ExternalLink className="h-3 w-3" />
          </a>
      );
  };

  // Re-add TxHash link function
  const renderTxHashLink = (hash: string | undefined | null) => {
      if (!hash) return 'N/A';
      const truncated = `${hash.substring(0, 8)}...${hash.substring(hash.length - 6)}`;
      return (
          <a href={`${filecoinExplorerTx}0x${hash}`} target="_blank" rel="noopener noreferrer" title={hash} className="inline-flex items-center gap-1 hover:underline text-blue-600">
              {truncated}
              <ExternalLink className="h-3 w-3" />
          </a>
      );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provenance Records</CardTitle>
        <CardDescription>
            {isConnected ? "On-chain provenance records associated with your connected address." : "Connect your wallet to view records."}
        </CardDescription>
      </CardHeader>
      <CardContent className="min-h-[300px] flex flex-col space-y-4">
        {isLoading ? (
            <div className="flex-grow flex items-center justify-center">
                 <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        ) : error ? (
            <div className="flex-grow flex items-center justify-center">
                 <p className="text-red-600">Error: {error}</p>
            </div>
        ) : !isConnected ? (
            <div className="flex-grow flex items-center justify-center">
                 <p className="text-muted-foreground">Please connect your wallet.</p>
            </div>
        ) : provenanceRecords.length > 0 ? (
            <ScrollArea className="h-[250px] flex-shrink-0"> 
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="w-[150px]">CID</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Tx Hash</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {provenanceRecords.map((record, index) => (
                    <TableRow key={record.filecoinCid + index + record.txHash} className={record.filecoinCid === previewCid ? 'bg-muted/50' : ''}>
                      <TableCell className="font-medium max-w-[150px] truncate" title={record.name}>{record.name || '-'}</TableCell>
                      <TableCell>{record.assetType}</TableCell>
                      <TableCell className="flex items-center space-x-1.5">
                         {renderCidLink(record.filecoinCid)}
                         {/* Copy Button */} 
                         <Button 
                             variant="ghost" 
                             size="icon" 
                             onClick={() => handleCopyCid(record.filecoinCid)} 
                             disabled={!record.filecoinCid}
                             title="Copy CID"
                             className="h-5 w-5 text-muted-foreground hover:text-foreground"
                         >
                             <Copy className="h-3 w-3" />
                         </Button>
                         {/* Show preview button only for Dataset types */} 
                         {record.assetType === 'Dataset' && (
                             <Button 
                                 variant="ghost" 
                                 size="icon"
                                 onClick={() => handlePreviewDataset(record.filecoinCid)} 
                                 disabled={isPreviewLoading && previewCid === record.filecoinCid} // Disable only if loading *this* preview
                                 title="Preview Dataset"
                                 className="h-5 w-5"
                             >
                                 {(isPreviewLoading && previewCid === record.filecoinCid) ? 
                                     <Loader2 className="h-3 w-3 animate-spin" /> : 
                                     "👁️"
                                 } 
                             </Button>
                         )}
                      </TableCell>
                      <TableCell>{formatTimestamp(record.timestamp)}</TableCell>
                      <TableCell>{renderTxHashLink(record.txHash)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollArea>
          ) : (
            <div className="flex-grow flex items-center justify-center">
                 <p className="text-muted-foreground">No provenance records found for this address.</p>
            </div>
        )}
        
        {/* --- Preview Section (appears below table if active) --- */} 
        {(previewCid || isPreviewLoading || previewError) && (
            <div className="mt-4 p-3 border rounded bg-muted/50 flex-shrink-0 relative">
                <Button 
                    variant="ghost"
                    size="icon"
                    onClick={closePreview}
                    className="absolute top-1 right-1 h-6 w-6"
                    title="Close Preview"
                >
                    <X className="h-4 w-4" />
                </Button>
                 <h4 className="text-sm font-medium mb-2">
                     Dataset Preview (CID: {previewCid ? `${previewCid.substring(0,6)}...${previewCid.substring(previewCid.length - 4)}` : 'Loading...'})
                 </h4>
                {previewError && (
                    <div className="p-3 border rounded bg-destructive/10">
                         <p className="text-sm text-destructive">Preview Error: {previewError}</p>
                    </div>
                )}
                {previewData && (
                    <ScrollArea className="h-[200px] border rounded">
                        <Table className="table-fixed w-full">
                            <TableHeader>
                                <TableRow>
                                    {previewData.headers.map((header, index) => (
                                        <TableHead key={index} className="whitespace-nowrap px-2 py-1 truncate" title={header}>{header}</TableHead>
                                    ))}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {previewData.rows.slice(0, 10).map((row, rowIndex) => (
                                    <TableRow key={rowIndex}>
                                        {row.map((cell, cellIndex) => (
                                            <TableCell key={cellIndex} className="whitespace-nowrap px-2 py-1 truncate" title={cell}>{cell}</TableCell>
                                        ))}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </ScrollArea>
                )}
                {isPreviewLoading && !previewError && (
                    <div className="p-3 border rounded bg-muted/50 flex items-center justify-center min-h-[50px]">
                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground text-sm">Loading preview...</span>
                    </div>
                )}
            </div>
        )}
      </CardContent>
       <CardFooter className="flex justify-end">
            <Button onClick={fetchProvenanceData} disabled={isLoading || !isConnected}>
                 {isLoading ? (
                    <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Refreshing...</>
                ) : (
                    'Refresh Data'
                 )}
            </Button>
       </CardFooter>
    </Card>
  );
} 