/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09439(unsigned int count)
{
    const unsigned int limit = 115u;
    return count > limit ? limit : count;
}
