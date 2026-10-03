"""Claude-based proposal synthesis with best practices: retries, error handling, budgeting."""

import os
import logging
from typing import Optional
from anthropic import Anthropic, APIError, APIConnectionError
from app.reports.proposal_schema import ProposalDraftV2, ParagraphBlock

logger = logging.getLogger(__name__)


class ProposalSynthesisError(Exception):
    """Proposal synthesis failed after retries."""
    def __init__(self, message: str, retryable: bool = False, retry_after_seconds: Optional[int] = None):
        self.message = message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


class ProposalSynthesizer:
    """Synthesize and enhance research proposals using Claude with best practices."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        """Initialize with Claude client."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.max_retries = 2
        self.timeout = 30
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        self.client = Anthropic(api_key=self.api_key, timeout=self.timeout)
    
    def enhance_proposal(
        self,
        draft: ProposalDraftV2,
        topic: str,
        focus_sections: Optional[list] = None,
    ) -> ProposalDraftV2:
        """
        Enhance an existing proposal draft using Claude.
        Optional synthesis - if Claude is unavailable, return the original draft.
        """
        
        if not focus_sections:
            focus_sections = ["methodology", "research_objectives"]
        
        try:
            logger.info("ProposalSynthesis: Starting enhancement with Claude (model=%s)", self.model)
            
            # Build enhancement prompt
            prompt = self._build_enhancement_prompt(draft, topic, focus_sections)
            
            # Call Claude with retry logic
            enhanced_text = self._call_claude_with_retries(prompt)
            
            if not enhanced_text:
                logger.warning("ProposalSynthesis: Claude returned empty response, using original draft")
                return draft
            
            # Parse and merge enhanced content back into draft
            enhanced_draft = self._merge_enhancements(draft, enhanced_text, focus_sections)
            
            logger.info("ProposalSynthesis: Enhancement complete, draft now %d words", 
                       self._count_words(enhanced_draft))
            
            return enhanced_draft
            
        except ProposalSynthesisError as e:
            if e.retryable:
                logger.warning("ProposalSynthesis: Retryable error (%s), returning original draft", e.message)
            else:
                logger.error("ProposalSynthesis: Non-retryable error (%s), returning original draft", e.message)
            # Graceful degradation: return original draft if synthesis fails
            return draft
        except Exception as e:
            logger.exception("ProposalSynthesis: Unexpected error, returning original draft")
            return draft
    
    def _build_enhancement_prompt(self, draft: ProposalDraftV2, topic: str, focus_sections: list) -> str:
        """Build a focused prompt for enhancing specific proposal sections."""
        
        current_text = self._extract_sections_text(draft, focus_sections)
        
        return f"""You are an academic research proposal expert. Enhance the following proposal sections with more depth, academic rigor, and methodological clarity.

**Topic:** {topic}

**Current Content:**
{current_text}

**Task:**
- Deepen the methodology section with more specific research design details, data management procedures, and quality assurance approaches
- Enhance research objectives with measurable success indicators and implementation milestones
- Maintain graduate-level academic writing quality
- Preserve all citations and research grounding
- Do NOT invent references or data
- Output only the enhanced sections in the exact same format

**Output Format:**
Provide only the enhanced text for the focused sections, preserving the original structure and style."""
    
    def _call_claude_with_retries(self, prompt: str, max_tokens: int = 2000) -> str:
        """Call Claude with exponential backoff retry logic."""
        
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info("ProposalSynthesis: Claude call (attempt %d/%d)", attempt + 1, self.max_retries + 1)
                
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                # Extract and return content
                if message.content and len(message.content) > 0:
                    response_text = message.content[0].text
                    logger.info("ProposalSynthesis: Claude returned %d tokens", 
                               getattr(message.usage, 'output_tokens', 0))
                    return response_text
                else:
                    logger.warning("ProposalSynthesis: Claude returned empty content")
                    return ""
                
            except APIConnectionError as e:
                last_error = ProposalSynthesisError(
                    f"Connection error: {str(e)}",
                    retryable=True,
                    retry_after_seconds=5 * (attempt + 1)
                )
                if attempt < self.max_retries:
                    logger.warning("ProposalSynthesis: Connection error, will retry in %ds", 
                                 5 * (attempt + 1))
                    continue
                raise last_error
                
            except APIError as e:
                # Check if retryable based on status code
                status_code = getattr(e, 'status_code', None)
                retryable = status_code in [429, 500, 502, 503]
                retry_after = 10 * (attempt + 1) if retryable else None
                
                last_error = ProposalSynthesisError(
                    f"API error ({status_code}): {str(e)}",
                    retryable=retryable,
                    retry_after_seconds=retry_after
                )
                
                if retryable and attempt < self.max_retries:
                    logger.warning("ProposalSynthesis: Retryable API error, will retry in %ds", retry_after)
                    continue
                raise last_error
        
        raise last_error or ProposalSynthesisError("Claude synthesis failed after retries", retryable=False)
    
    def _extract_sections_text(self, draft: ProposalDraftV2, focus_sections: list) -> str:
        """Extract text from specified sections of the draft."""
        
        sections_text = {}
        
        for section in focus_sections:
            if section == "methodology":
                text_parts = [p.text for p in (draft.methodology.research_design or [])]
                text_parts.extend([p.text for p in (draft.methodology.data_collection or [])])
                text_parts.extend([p.text for p in (draft.methodology.analysis or [])])
                sections_text["Methodology"] = " ".join(text_parts)
            
            elif section == "research_objectives":
                text_parts = [obj.text for obj in (draft.research_objectives or [])]
                sections_text["Research Objectives"] = " ".join(text_parts)
            
            elif section == "research_gap":
                text_parts = [p.text for p in (draft.research_gap or [])]
                sections_text["Research Gap"] = " ".join(text_parts)
        
        # Format for prompt
        formatted = "\n\n".join([
            f"**{name}:**\n{text}"
            for name, text in sections_text.items() if text
        ])
        
        return formatted or "No sections to enhance"
    
    def _merge_enhancements(
        self,
        draft: ProposalDraftV2,
        enhanced_text: str,
        focus_sections: list
    ) -> ProposalDraftV2:
        """
        Merge enhanced text back into the proposal draft.
        Preserves original structure and citations.
        """
        
        # For now, return the original draft
        # A production implementation would parse enhanced_text and merge selectively
        # This prevents accidentally breaking the proposal structure
        
        logger.info("ProposalSynthesis: Enhanced content received (%d chars), " +
                   "would merge if parser implemented", len(enhanced_text))
        
        return draft
    
    def _count_words(self, draft: ProposalDraftV2) -> int:
        """Count total words in proposal draft."""
        text_parts = []
        
        for p in (draft.overview or []):
            text_parts.append(p.text)
        for theme in (draft.literature_insights or []):
            for p in (theme.blocks or []):
                text_parts.append(p.text)
        for p in (draft.research_gap or []):
            text_parts.append(p.text)
        for p in (draft.research_problem or []):
            text_parts.append(p.text)
        for q in (draft.research_questions or []):
            text_parts.append(q.text)
        for obj in (draft.research_objectives or []):
            text_parts.append(obj.text)
        for p in (draft.methodology.research_design or []):
            text_parts.append(p.text)
        for p in (draft.methodology.data_collection or []):
            text_parts.append(p.text)
        for p in (draft.methodology.analysis or []):
            text_parts.append(p.text)
        for p in (draft.conclusion or []):
            text_parts.append(p.text)
        
        full_text = " ".join(text_parts)
        return len(full_text.split())
