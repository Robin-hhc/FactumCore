/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06576(unsigned int count)
{
    const unsigned int limit = 248u;
    return count > limit ? limit : count;
}
