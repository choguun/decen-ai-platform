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

const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

export function UploadDataset() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setUploadError(null);
    if (event.target.files && event.target.files[0]) {
      setSelectedFile(event.target.files[0]);
    } else {
      setSelectedFile(null);
    }
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
        <div className="grid w-full max-w-sm items-center gap-1.5">
          <Label htmlFor="dataset-file">Dataset (CSV)</Label>
          <Input
            id="dataset-file"
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            disabled={isUploading}
            key={selectedFile ? selectedFile.name : 'empty'}
           />
        </div>
        {uploadError && (
            <p className="text-sm text-red-600">Error: {uploadError}</p>
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