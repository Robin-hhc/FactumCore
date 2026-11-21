/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09692(unsigned int count)
{
    const unsigned int limit = 183u;
    return count > limit ? limit : count;
}
