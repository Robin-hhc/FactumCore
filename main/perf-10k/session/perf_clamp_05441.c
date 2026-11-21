/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05441(unsigned int count)
{
    const unsigned int limit = 126u;
    return count > limit ? limit : count;
}
