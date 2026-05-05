import { PresentationFile, Presentation } from '@oai/artifact-tool';
console.log('PresentationFile static', Object.getOwnPropertyNames(PresentationFile));
console.log('Presentation proto', Object.getOwnPropertyNames(PresentationFile.prototype));
console.log('Presentation static', Object.getOwnPropertyNames(Presentation));
