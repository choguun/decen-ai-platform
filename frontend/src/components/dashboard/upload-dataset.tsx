'use client'

import React, { useState } from 'react';
import axios, { isAxiosError } from 'axios';
import { toast } from 'sonner';
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getAuthToken } from "@/components/auth/connect-wallet-button";
import { Loader2 } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// Type for preview data
interface PreviewData {
    headers: string[];
    rows: string[][];
}

export function UploadDataset() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  // --- Preview State --- 
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
      // Clear preview when file changes
      setPreviewData(null);
      setPreviewError(null);
    } else {
      setSelectedFile(null);
      setPreviewData(null);
      setPreviewError(null);
    }
  };

// --- Function to handle Dataset Preview from local file --- 
 const handlePreviewDataset = () => {
    if (!selectedFile) {
        toast.error("Please select a file first.");
        return;
    }

    setIsPreviewLoading(true);
    setPreviewError(null);
    setPreviewData(null);

    const reader = new FileReader();

    reader.onload = (e) => {
        try {
            const csvText = e.target?.result as string;
            if (!csvText) {
                throw new Error("File content is empty or unreadable.");
            }
            // Basic CSV Parsing (similar to TrainModel)
            const lines = csvText.trim().split('\n');
            if (lines.length === 0) {
                setPreviewData({ headers: [], rows: [] });
                return; // No error, just empty
            }

            const headers = lines[0].split(',').map(h => h.trim());
            const rows = lines.slice(1).map(line => line.split(',').map(cell => cell.trim()));

            setPreviewData({ headers, rows });
            toast.success("Dataset preview loaded.");
        } catch (error: unknown) {
            console.error("Dataset preview parsing error:", error);
            let detail = "Failed to parse CSV preview.";
            if (error instanceof Error) {
                detail = error.message;
            }
            setPreviewError(detail);
            toast.error(detail);
        } finally {
             setIsPreviewLoading(false);
        }
    };

    reader.onerror = (e) => {
        console.error("File reading error:", e);
        const detail = "Failed to read the selected file.";
        setPreviewError(detail);
        toast.error(detail);
        setIsPreviewLoading(false);
    };

    reader.readAsText(selectedFile); // Read the selected local file
 };

  const handleUpload = async () => {
    if (!selectedFile) {
      toast.error("Please select a CSV file first.");
      setUploadError("Please select a CSV file first.");
      return;
    }

    const token = getAuthToken();
    if (!token) {
      toast.error("Please sign in with your wallet first.");
      setUploadError("Authentication required. Please sign in.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await axios.post(`${backendUrl}/data/upload/dataset`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.data && response.data.cid) {
        toast.success(`Dataset uploaded successfully! CID: ${response.data.cid}`);
        setSelectedFile(null);
      } else {
        throw new Error("Upload failed: Invalid response from server.");
      }
    } catch (error: unknown) {
      console.error("Upload error:", error);
       let detail = "An unknown error occurred during upload."
      if (isAxiosError(error)) {
        detail = error.response?.data?.detail || error.message
      } else if (error instanceof Error) {
        detail = error.message
      }
      setUploadError(detail);
      toast.error(`Upload failed: ${detail}`);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Dataset</CardTitle>
        <CardDescription>Upload a CSV dataset file to start.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* --- File Input and Preview Button --- */}
        <div className="space-y-1.5">
            <Label htmlFor="dataset-file">Dataset (CSV)</Label>
            <div className="flex space-x-2">
               <Input
                   id="dataset-file"
                   type="file"
                   accept=".csv"
                   onChange={handleFileChange}
                   disabled={isUploading || isPreviewLoading}
                   key={selectedFile ? selectedFile.name : 'empty'} // Reset input if file is cleared
               />
                <Button 
                   variant="outline" 
                   size="icon" 
                   onClick={handlePreviewDataset} 
                   disabled={!selectedFile || isPreviewLoading || isUploading}
                   title="Preview Selected File"
               >
                    {isPreviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "👁️"} 
               </Button>
           </div>
        </div>
        {uploadError && (
            <p className="text-sm text-red-600">Error: {uploadError}</p>
        )}

        {/* --- Preview Display Area --- */}
        {previewError && (
           <div className="mt-2 p-3 border rounded bg-destructive/10">
                <p className="text-sm text-destructive">Preview Error: {previewError}</p>
           </div>
        )}
        {previewData && (
           <div className="mt-2">
                <h5 className="text-sm font-medium mb-1">Dataset Preview (First 10 Rows)</h5>
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
            </div>
        )}
        {isPreviewLoading && !previewError && (
            <div className="mt-2 p-3 border rounded bg-muted/50 flex items-center justify-center min-h-[50px]">
               <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
               <span className="ml-2 text-muted-foreground text-sm">Loading preview...</span>
            </div>
        )}
      </CardContent>
      <CardFooter>
        <Button onClick={handleUpload} disabled={!selectedFile || isUploading}>
          {isUploading ? (
            <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Uploading...</>
          ) : (
            'Upload'
          )}
        </Button>
      </CardFooter>
    </Card>
  );
} 