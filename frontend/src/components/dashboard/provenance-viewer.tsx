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
import { Loader2, ExternalLink } from 'lucide-react';

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';
const ipfsGateway = 'https://files.lighthouse.storage/viewFile/';
const filecoinExplorerTx = 'https://calibration.filscan.io/en/message/'; // Explorer URL

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

export function ProvenanceViewer() {
  const { address, isConnected } = useAccount();
  const [provenanceRecords, setProvenanceRecords] = useState<AssetRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      <CardContent className="min-h-[350px] flex flex-col">
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
            <ScrollArea className="h-[300px]"> 
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>CID</TableHead>
                    <TableHead>Timestamp</TableHead>
                    <TableHead>Tx Hash</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {provenanceRecords.map((record, index) => (
                    <TableRow key={record.filecoinCid + index + record.txHash}>
                      <TableCell className="font-medium max-w-[150px] truncate" title={record.name}>{record.name || '-'}</TableCell>
                      <TableCell>{record.assetType}</TableCell>
                      <TableCell>{renderCidLink(record.filecoinCid)}</TableCell>
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