'use client' // Most interactive parts will be client components

import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import React, { useState, useEffect, useRef, ChangeEvent } from 'react'; // Import React and useState, useEffect, useRef, ChangeEvent
import axios, { isAxiosError } from 'axios'; // Import axios
import { toast } from 'sonner'; // Import toast
import { getAuthToken } from "@/components/auth/connect-wallet-button"; // Import helper
import { Textarea } from "@/components/ui/textarea"; // Use Textarea for JSON input
import { isAddress } from 'viem'; // Import utility for address check
import { useAccount } from 'wagmi'; // Need for ProvenanceViewer address check
import { ScrollArea } from "@/components/ui/scroll-area"; // Needed for ProvenanceViewer table

// Import dashboard components
import { UploadDataset } from '@/components/dashboard/upload-dataset';
import { TrainModel } from '@/components/dashboard/train-model';
import { Inference } from '@/components/dashboard/inference';
import { ProvenanceViewer } from '@/components/dashboard/provenance-viewer';

// Get backend URL from environment variable
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

// --- Type Definitions (Matching Backend Models) ---
interface TrainingStatus {
  job_id: string;
  status: string; // PENDING, DOWNLOADING, TRAINING, UPLOADING_MODEL, etc.
  message?: string;
  dataset_cid: string;
  owner_address: string;
  model_cid?: string;
  model_info_cid?: string;
  accuracy?: number;
  fvm_tx_hash?: string;
  created_at?: string; // Represent dates as strings for simplicity here
  updated_at?: string;
}

interface InferenceResult {
  prediction: any; // Keep prediction flexible for now
  probabilities?: Record<string, number>;
  model_cid: string;
}

interface AssetRecord {
    txHash: string; // Transaction hash of registration - Match ProvenanceViewer's interface
    blockNumber: number; // Match ProvenanceViewer's interface
    timestamp: number; // Consider formatting this
    ownerAddress: string; // Match ProvenanceViewer's interface
    assetType: 'Dataset' | 'Model'; // Match ProvenanceViewer's interface
    assetCid: string; // Match ProvenanceViewer's interface
    relatedCid?: string; // e.g., Dataset CID for a Model - Match ProvenanceViewer's interface
    metadataCid?: string; // Optional metadata CID - Match ProvenanceViewer's interface
}

export default function Home() {
  return (
    <div className="flex min-h-screen w-full flex-col">
      <Header />
      <main className="flex flex-1 flex-col gap-4 p-4 md:gap-8 md:p-8 container max-w-screen-lg">
        <h1 className="text-2xl font-semibold">VeriFAI Dashboard</h1>
        <Tabs defaultValue="upload" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="upload">1. Upload Dataset</TabsTrigger>
            <TabsTrigger value="train">2. Train Model</TabsTrigger>
            <TabsTrigger value="infer">3. Inference</TabsTrigger>
            <TabsTrigger value="provenance">4. View Provenance</TabsTrigger>
          </TabsList>
          <TabsContent value="upload">
            <UploadDataset />
          </TabsContent>
          <TabsContent value="train">
            <TrainModel />
          </TabsContent>
          <TabsContent value="infer">
            <Inference />
          </TabsContent>
          <TabsContent value="provenance">
            <ProvenanceViewer />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
} 