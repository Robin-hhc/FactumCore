/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08596(unsigned int count)
{
    const unsigned int limit = 226u;
    return count > limit ? limit : count;
}
