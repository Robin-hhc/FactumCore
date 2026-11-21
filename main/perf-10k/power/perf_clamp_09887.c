/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09887(unsigned int count)
{
    const unsigned int limit = 12u;
    return count > limit ? limit : count;
}
