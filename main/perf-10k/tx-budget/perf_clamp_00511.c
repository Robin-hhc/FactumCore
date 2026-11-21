/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_00511(unsigned int count)
{
    const unsigned int limit = 229u;
    return count > limit ? limit : count;
}
